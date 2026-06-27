"""CLI to ingest a single PDF into the knowledge base.

For bulk-ingesting the whole corpus/ tree, use scripts/ingest_corpus.py
(or `make seed`) instead.

Usage:
    uv run python scripts/ingest_pdf.py \
        --path corpus/nasa_payload_guides/iss_benefits_humanity.pdf \
        --source-type nasa_payload_guide \
        --title "Benefits for Humanity from the ISS" \
        --source-url "https://www.nasa.gov/..."
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from apps.api.logging_config import configure_logging
from packages.kb.ingestion.pipeline import ingest_pdf
from packages.kb.models.schemas import DocumentMetadata


async def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest a PDF into the knowledge base")
    parser.add_argument("--path", required=True, type=Path)
    parser.add_argument("--source-type", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--organization", default=None)
    args = parser.parse_args()

    configure_logging()

    metadata = DocumentMetadata(
        source_url=args.source_url,
        source_type=args.source_type,
        title=args.title,
        organization=args.organization,
    )

    result = await ingest_pdf(args.path, metadata)
    print()
    print("Ingestion result:")
    print(f"  Document ID: {result.document_id}")
    print(f"  Title: {result.title}")
    print(f"  Chunks inserted: {result.chunks_inserted}")
    print(f"  Skipped (already existed): {result.skipped_existing}")
    print(f"  Duration: {result.duration_seconds:.1f}s")


if __name__ == "__main__":
    asyncio.run(main())
