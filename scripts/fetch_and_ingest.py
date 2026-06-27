"""Fetch authoritative source PDFs from a discovery manifest, verify each is a
real text-bearing PDF, dedup by content checksum, and ingest into the KB.

The manifest is a JSON object with a ``candidates`` array (as produced by the
corpus-source-discovery workflow), each entry having ``title``, ``url``,
``source_type``, ``topic``, ``why_relevant``. We download every URL, verify it,
store it under ``corpus/<subdir>/`` and run it through the standard ingestion
pipeline with real provenance (the original ``source_url``). A provenance line
per ingested doc is appended to ``corpus/_provenance.jsonl``.

Usage:
    uv run python scripts/fetch_and_ingest.py --source-json /path/to/manifest.json
    uv run python scripts/fetch_and_ingest.py --source-json m.json --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import ssl
import urllib.request
from pathlib import Path

from apps.api.logging_config import configure_logging
from packages.kb.ingestion.loaders import compute_file_checksum
from packages.kb.ingestion.pipeline import ingest_pdf
from packages.kb.models.schemas import DocumentMetadata

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def map_source(candidate: dict) -> tuple[str, str]:
    """Map a workflow source_type to (system source_type, corpus subdir).

    System source_types must match the retrieval profiles in
    packages/kb/agents/profiles.py or the docs won't be retrievable.
    """
    st = (candidate.get("source_type") or "").strip()
    blob = " ".join(str(candidate.get(k, "")) for k in ("title", "topic", "why_relevant")).lower()

    if st == "hardware_spec":
        return "hardware_spec", "hardware_specs"
    if st == "research_paper":
        return "paper", "papers"
    if st == "iss_annual_report":
        return "iss_annual_report", "annual_reports"
    if st == "regulatory_doc":
        return "regulatory", "regulatory"
    if st == "safety_guide":
        # Biosafety/containment references serve the regulatory+safety agents;
        # payload-process docs serve the payload-guide-scoped agents.
        biosafety = (
            "bmbl",
            "biosafety",
            "select agent",
            "cfr",
            "containment",
            "recombinant",
            "bsl",
        )
        if any(k in blob for k in biosafety):
            return "regulatory", "regulatory"
        return "nasa_payload_guide", "nasa_payload_guides"
    if st == "mission_guide":
        if "casis" in blob or "national lab" in blob:
            return "casis_solicitation", "casis"
        return "nasa_payload_guide", "nasa_payload_guides"
    return "paper", "papers"


def slugify(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", (text or "").strip().lower()).strip("-")
    return (s or "doc")[:80]


def load_candidates(path: Path) -> list[dict]:
    raw = path.read_text()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        data = json.loads(raw[start:])
    if isinstance(data, list):
        return data
    # Accept either a bare {candidates:[...]} or the workflow task-output
    # envelope {summary, logs, result: {candidates:[...]}}.
    if "candidates" in data:
        return data["candidates"]
    result = data.get("result")
    if isinstance(result, dict):
        return result.get("candidates", [])
    return []


def download(url: str, dest: Path) -> int:
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "application/pdf,*/*"})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=90, context=ctx) as resp:
        data = resp.read()
    dest.write_bytes(data)
    return len(data)


def verify_pdf(path: Path) -> tuple[bool, int, int, str]:
    """Return (ok, pages, sampled_chars, reason)."""
    head = path.read_bytes()[:5]
    if not head.startswith(b"%PDF-"):
        return False, 0, 0, "not a PDF (bad magic bytes)"
    size = path.stat().st_size
    if size < 8000:
        return False, 0, 0, f"too small ({size} bytes)"
    try:
        import pypdf

        reader = pypdf.PdfReader(str(path))
        pages = len(reader.pages)
        text = ""
        for page in reader.pages[:6]:
            text += page.extract_text() or ""
            if len(text) > 500:
                break
        if pages < 1:
            return False, pages, len(text), "0 pages"
        if len(text.strip()) < 120:
            return False, pages, len(text.strip()), "no extractable text (scanned/encrypted?)"
        return True, pages, len(text.strip()), "ok"
    except Exception as exc:  # malformed PDF
        return False, 0, 0, f"pypdf error: {type(exc).__name__}: {exc}"


def existing_checksums(corpus_dir: Path) -> set[str]:
    return {compute_file_checksum(p) for p in corpus_dir.rglob("*.pdf")}


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-json", required=True, type=Path)
    parser.add_argument("--corpus-dir", default=Path("corpus"), type=Path)
    parser.add_argument("--strategy", default="fast", help="PDF parse strategy (fast|hi_res)")
    parser.add_argument("--limit", type=int, default=0, help="0 = no limit")
    parser.add_argument("--dry-run", action="store_true", help="download+verify only, no ingest")
    args = parser.parse_args()

    configure_logging()
    candidates = load_candidates(args.source_json)
    if args.limit:
        candidates = candidates[: args.limit]

    args.corpus_dir.mkdir(exist_ok=True)
    seen_checksums = existing_checksums(args.corpus_dir)
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    provenance_path = args.corpus_dir / "_provenance.jsonl"

    n_ok = n_skip_dup = n_bad = n_dl_fail = n_ingested = n_skip_existing = 0
    print(f"Processing {len(candidates)} candidate(s) (strategy={args.strategy})\n")

    for i, cand in enumerate(candidates, start=1):
        url = (cand.get("url") or "").strip()
        title = (cand.get("title") or "untitled").strip()
        if not url or url.lower() in seen_urls:
            continue
        seen_urls.add(url.lower())
        label = f"[{i}/{len(candidates)}] {title[:64]}"

        # Near-duplicate guard: mirrors/alternate copies of the same document
        # share a title prefix but differ in bytes (checksum won't catch them).
        title_key = re.sub(r"[^a-z0-9]+", "", title.lower())[:45]
        if title_key in seen_titles:
            n_skip_dup += 1
            print(f"{label}\n    duplicate title (alternate copy) — skipping")
            continue
        seen_titles.add(title_key)

        source_type, subdir = map_source(cand)
        subdir_path = args.corpus_dir / subdir
        subdir_path.mkdir(parents=True, exist_ok=True)
        dest = subdir_path / f"{slugify(title)}.pdf"

        try:
            nbytes = download(url, dest)
        except Exception as exc:
            n_dl_fail += 1
            print(f"{label}\n    DOWNLOAD FAILED: {type(exc).__name__}: {str(exc)[:120]}")
            dest.unlink(missing_ok=True)
            continue

        ok, pages, chars, reason = verify_pdf(dest)
        if not ok:
            n_bad += 1
            print(f"{label}\n    REJECTED: {reason} ({nbytes} bytes)")
            dest.unlink(missing_ok=True)
            continue

        checksum = compute_file_checksum(dest)
        if checksum in seen_checksums:
            n_skip_dup += 1
            print(f"{label}\n    duplicate content (checksum already in corpus) — removing")
            dest.unlink(missing_ok=True)
            continue
        seen_checksums.add(checksum)
        n_ok += 1
        print(f"{label}\n    OK: {pages}p, {chars} chars sampled -> {source_type}/{dest.name}")

        with provenance_path.open("a") as fh:
            fh.write(
                json.dumps(
                    {
                        "title": title,
                        "url": url,
                        "source_type": source_type,
                        "path": str(dest),
                        "pages": pages,
                        "bytes": nbytes,
                        "checksum": checksum,
                    }
                )
                + "\n"
            )

        if args.dry_run:
            continue

        metadata = DocumentMetadata(source_url=url, source_type=source_type, title=title)
        try:
            result = await ingest_pdf(dest, metadata, strategy=args.strategy)
        except Exception as exc:
            print(f"    INGEST FAILED: {type(exc).__name__}: {str(exc)[:160]}")
            continue
        if result.skipped_existing:
            n_skip_existing += 1
            print("    ingest: skipped (already in DB)")
        else:
            n_ingested += 1
            print(f"    ingest: {result.chunks_inserted} chunks in {result.duration_seconds:.1f}s")

    print(
        f"\nDone. verified_ok={n_ok} ingested={n_ingested} "
        f"skipped_existing={n_skip_existing} dup={n_skip_dup} "
        f"rejected={n_bad} download_failed={n_dl_fail}"
    )


if __name__ == "__main__":
    asyncio.run(main())
