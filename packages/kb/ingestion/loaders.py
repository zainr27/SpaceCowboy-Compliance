from __future__ import annotations

import hashlib
from pathlib import Path

import structlog
from unstructured.partition.pdf import partition_pdf

logger = structlog.get_logger(__name__)


def compute_file_checksum(path: Path) -> str:
    """SHA-256 hex digest of a file, used as a deduplication key."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def load_pdf_elements(path: Path, strategy: str = "hi_res") -> list:
    """Parse a PDF into structured elements using unstructured.

    Returns a list of unstructured.documents.elements.Element objects,
    each with .text, .metadata.page_number, and a category like 'Title',
    'NarrativeText', 'Table', etc.

    strategy="hi_res" requires poppler (brew install poppler) and downloads a
    layout-detection model on first run. Falls back to "fast" if poppler is
    missing. strategy="fast" is fine for development; use "hi_res" for production
    ingestion of NASA/CASIS documents with complex layouts.
    """
    logger.info("loading_pdf", path=str(path), strategy=strategy)
    try:
        elements = partition_pdf(
            filename=str(path),
            strategy=strategy,
            infer_table_structure=True,
            extract_images_in_pdf=False,
            # Keep these false unless you specifically need them; they're slow
            extract_image_block_types=[],
        )
    except Exception as exc:
        if strategy != "fast":
            logger.warning(
                "pdf_strategy_failed_falling_back",
                strategy=strategy,
                error=str(exc),
                fallback="fast",
            )
            return load_pdf_elements(path, strategy="fast")
        raise

    # unstructured "fast" silently returns [] when pdfminer finds no text layers;
    # fall through to pypdf-based extraction as a final safety net
    if not elements:
        logger.warning("unstructured_returned_no_elements", path=str(path), strategy=strategy)
        return _load_via_pypdf(path)

    logger.info(
        "loaded_pdf",
        path=str(path),
        element_count=len(elements),
        categories=_category_counts(elements),
    )
    return elements


def _load_via_pypdf(path: Path) -> list:
    """Fallback: extract text page-by-page using pypdf, return lightweight element dicts."""
    import pypdf
    from unstructured.documents.elements import NarrativeText

    logger.info("loading_pdf_via_pypdf_fallback", path=str(path))
    reader = pypdf.PdfReader(str(path))
    elements = []
    for page_num, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        text = text.strip()
        if text:
            el = NarrativeText(text=text)
            el.metadata.page_number = page_num
            elements.append(el)
    logger.info("loaded_pdf_via_pypdf", path=str(path), pages=len(elements))
    return elements


def _category_counts(elements: list) -> dict[str, int]:
    """Count elements by category for logging visibility."""
    counts: dict[str, int] = {}
    for el in elements:
        cat = el.category if hasattr(el, "category") else type(el).__name__
        counts[cat] = counts.get(cat, 0) + 1
    return counts
