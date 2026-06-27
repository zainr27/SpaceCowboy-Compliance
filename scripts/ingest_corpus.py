"""Bulk-ingest every PDF under ``corpus/`` into the knowledge base.

Recursively finds all ``*.pdf`` files under the corpus directory and ingests
each one through the existing single-PDF pipeline (``ingest_pdf``). Documents
that have already been ingested are skipped automatically via the pipeline's
checksum-based dedup, so this script is safe to re-run.

The corpus PDFs are gitignored (see ``.gitignore``), so a fresh clone has an
empty ``corpus/`` tree and an empty knowledge base. Drop PDFs into the
subdirectories under ``corpus/`` (e.g. ``corpus/nasa_payload_guides/``) and run
this script — or ``make seed`` — to populate the KB.

Usage:
    uv run python scripts/ingest_corpus.py
    uv run python scripts/ingest_corpus.py --corpus-dir corpus
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from apps.api.logging_config import configure_logging
from packages.kb.ingestion.pipeline import ingest_pdf
from packages.kb.models.schemas import DocumentMetadata

# Maps each corpus subdirectory to a knowledge-base source_type. PDFs that live
# directly under corpus/ or in an unmapped subdirectory fall back to "paper".
SUBDIR_SOURCE_TYPE: dict[str, str] = {
    "nasa_payload_guides": "nasa_payload_guide",
    "nasa_reports": "iss_annual_report",
    "annual_reports": "iss_annual_report",
    "hardware_specs": "hardware_spec",
    "manifests": "nasa_payload_guide",
    "papers": "paper",
}
DEFAULT_SOURCE_TYPE = "paper"


def source_type_for(pdf_path: Path, corpus_dir: Path) -> str:
    """Infer a source_type from the first path component under corpus_dir."""
    try:
        relative = pdf_path.relative_to(corpus_dir)
    except ValueError:
        return DEFAULT_SOURCE_TYPE
    if len(relative.parts) < 2:
        return DEFAULT_SOURCE_TYPE
    return SUBDIR_SOURCE_TYPE.get(relative.parts[0], DEFAULT_SOURCE_TYPE)


def title_for(pdf_path: Path) -> str:
    """Derive a human-readable title from the file stem."""
    return pdf_path.stem.replace("_", " ").replace("-", " ").strip()


async def main() -> None:
    parser = argparse.ArgumentParser(description="Bulk-ingest all PDFs under the corpus directory.")
    parser.add_argument(
        "--corpus-dir",
        type=Path,
        default=Path("corpus"),
        help="Directory to search recursively for PDFs (default: corpus)",
    )
    args = parser.parse_args()

    configure_logging()

    corpus_dir = args.corpus_dir
    if not corpus_dir.exists():
        print(f"Corpus directory not found: {corpus_dir.resolve()}")
        print(
            "Corpus PDFs are gitignored (see .gitignore), so a fresh clone has "
            "no PDFs. Create the directory and add PDFs under it, e.g. "
            f"{corpus_dir}/nasa_payload_guides/your_doc.pdf"
        )
        return

    pdf_paths = sorted(corpus_dir.rglob("*.pdf"))
    if not pdf_paths:
        print(f"No PDFs found under {corpus_dir.resolve()}")
        print(
            "Corpus PDFs are gitignored (see .gitignore: corpus/**/*.pdf), so a "
            "fresh clone starts with an empty knowledge base."
        )
        print(
            "Add PDFs under the corpus subdirectories and re-run, e.g.:\n"
            f"  {corpus_dir}/nasa_payload_guides/iss_benefits_humanity.pdf\n"
            f"  {corpus_dir}/hardware_specs/redwire-mvp-flysheet.pdf\n"
            f"  {corpus_dir}/papers/plant_water_management_microgravity.pdf"
        )
        return

    total = len(pdf_paths)
    print(f"Found {total} PDF(s) under {corpus_dir.resolve()}\n")

    ingested = 0
    skipped = 0
    failed = 0

    for index, pdf_path in enumerate(pdf_paths, start=1):
        source_type = source_type_for(pdf_path, corpus_dir)
        metadata = DocumentMetadata(
            source_url=pdf_path.resolve().as_uri(),
            source_type=source_type,
            title=title_for(pdf_path),
        )
        print(f"[{index}/{total}] {pdf_path} (type={source_type})")
        try:
            result = await ingest_pdf(pdf_path, metadata)
        except Exception as exc:  # keep going through the rest of the corpus
            failed += 1
            print(f"    FAILED: {type(exc).__name__}: {exc}")
            continue

        if result.skipped_existing:
            skipped += 1
            print("    skipped (already ingested)")
        else:
            ingested += 1
            print(
                f"    ingested: {result.chunks_inserted} chunks in {result.duration_seconds:.1f}s"
            )

    print(f"\nDone. {ingested} ingested, {skipped} skipped, {failed} failed (of {total} total).")


if __name__ == "__main__":
    asyncio.run(main())
