"""Detect PDFs that require OCR (image-based, low text density)."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pdfplumber


_MIN_CHARS_PER_PAGE = 50


def needs_ocr(pdf_path: Path, sample_pages: int = 5) -> tuple[bool, str]:
    """Check if a PDF is image-based and requires OCR.

    Args:
        pdf_path:     Path to the PDF file.
        sample_pages: Number of pages to sample (evenly spread).

    Returns:
        (needs_ocr, reason) — reason is empty string if OCR not needed.
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            n_pages = len(pdf.pages)
            if n_pages == 0:
                return True, "PDF has no pages"

            # Sample pages evenly
            step = max(1, n_pages // sample_pages)
            pages_to_check = list(range(0, n_pages, step))[:sample_pages]

            total_chars = 0
            for page_idx in pages_to_check:
                text = pdf.pages[page_idx].extract_text() or ""
                total_chars += len(text.replace(" ", "").replace("\n", ""))

            avg_chars = total_chars / len(pages_to_check)

            if avg_chars < _MIN_CHARS_PER_PAGE:
                return True, f"Low text density: avg {avg_chars:.0f} chars/page (threshold {_MIN_CHARS_PER_PAGE})"

        return False, ""

    except Exception as exc:
        return True, f"Could not read PDF: {type(exc).__name__}: {exc}"
