"""PDF downloader with validation, hashing, and resume support."""
from __future__ import annotations

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF
import requests

from src.config import SCRAPER, PATHS
from src.parsers.report_parser import DownloadStatus, ReportRecord
from src.scrapers.base import BaseSession
from src.utils.hashing import sha256_file
from src.utils.normalization import sanitize_filename

logger = logging.getLogger(__name__)

_PDF_MAGIC = b"%PDF"
_MIN_FILE_SIZE = 1024  # 1 KB minimum


class PDFDownloader:
    """
    Downloads, validates, and stores annual report PDFs.
    Supports idempotent re-runs (skip already downloaded + valid PDFs).
    """

    def __init__(self, session: BaseSession | None = None) -> None:
        self.session = session or BaseSession()

    # ─── Public API ─────────────────────────────────────────────────────────

    def download(self, report: ReportRecord, dry_run: bool = False) -> ReportRecord:
        """
        Download and validate the PDF for a report.
        Updates report in-place and returns it.
        """
        if not report.document_url:
            report.download_status = DownloadStatus.FAILED
            report.error = "No document URL available"
            return report

        dest_path = self._build_path(report)

        # Check if already downloaded and valid
        if dest_path.exists():
            existing_check = self._check_existing(dest_path, report)
            if existing_check:
                return report

        if dry_run:
            logger.info("[DRY-RUN] Would download: %s → %s", report.document_url, dest_path)
            report.download_status = DownloadStatus.PENDING
            report.local_path = str(dest_path)
            report.file_name = dest_path.name
            return report

        # Download
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info("Downloading %s %s → %s", report.company_name, report.year, dest_path.name)

        try:
            self._download_to_file(report.document_url, dest_path)
        except Exception as e:
            logger.error("Download failed for %s %s: %s", report.company_name, report.year, e)
            report.download_status = DownloadStatus.FAILED
            report.error = str(e)
            # Remove partial file
            if dest_path.exists():
                dest_path.unlink()
            return report

        # Validate
        validation_error = self._validate_pdf(dest_path)
        if validation_error:
            logger.error(
                "PDF validation failed for %s %s: %s",
                report.company_name, report.year, validation_error,
            )
            dest_path.unlink(missing_ok=True)
            report.download_status = DownloadStatus.INVALID_PDF
            report.error = validation_error
            return report

        # Success
        self._populate_metadata(report, dest_path)
        logger.info(
            "Downloaded %s %s (%d pages, %.1f MB)",
            report.company_name, report.year,
            report.pdf_pages, report.file_size / 1_048_576,
        )
        return report

    # ─── Internals ──────────────────────────────────────────────────────────

    def _build_path(self, report: ReportRecord) -> Path:
        """Construct the local filesystem path for this report."""
        sector_dir = sanitize_filename(report.sector) if report.sector else "UNKNOWN_SECTOR"
        company_dir = sanitize_filename(report.company_name)
        year_dir = str(report.year)
        return PATHS.reports_dir / sector_dir / company_dir / year_dir / "annual_report.pdf"

    def _check_existing(self, path: Path, report: ReportRecord) -> bool:
        """
        If file exists, validate it. Return True if valid (skip download).
        Delete and return False if invalid (trigger re-download).
        """
        err = self._validate_pdf(path)
        if err:
            logger.warning("Existing file invalid (%s), re-downloading: %s", err, path)
            path.unlink(missing_ok=True)
            return False

        self._populate_metadata(report, path)
        report.download_status = DownloadStatus.SKIPPED
        logger.info("Already exists and valid: %s %s – SKIP", report.company_name, report.year)
        return True

    def _download_to_file(self, url: str, dest: Path) -> None:
        """Stream download with retry on connection errors."""
        resp = self.session.session.get(
            url,
            timeout=SCRAPER.timeout,
            stream=True,
            headers={"Accept": "application/pdf,*/*"},
        )
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "")
        if "html" in content_type and "pdf" not in content_type:
            raise ValueError(f"Expected PDF but got Content-Type: {content_type}")

        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)

        if dest.stat().st_size < _MIN_FILE_SIZE:
            raise ValueError(f"Downloaded file too small: {dest.stat().st_size} bytes")

    @staticmethod
    def _validate_pdf(path: Path) -> Optional[str]:
        """
        Validate PDF integrity. Returns error message string or None if valid.
        Checks: existence, size, PDF magic bytes, openable with PyMuPDF, page count.
        """
        if not path.exists():
            return "File does not exist"

        if path.stat().st_size < _MIN_FILE_SIZE:
            return f"File too small: {path.stat().st_size} bytes"

        # Check PDF magic header
        try:
            with open(path, "rb") as f:
                header = f.read(4)
            if header != _PDF_MAGIC:
                return f"Invalid PDF magic bytes: {header!r}"
        except OSError as e:
            return f"Cannot read file: {e}"

        # Try to open with PyMuPDF
        try:
            doc = fitz.open(str(path))
            pages = len(doc)
            doc.close()
            if pages == 0:
                return "PDF has 0 pages"
        except Exception as e:
            return f"PyMuPDF error: {e}"

        return None

    def _populate_metadata(self, report: ReportRecord, path: Path) -> None:
        """Fill report metadata from the validated PDF file."""
        report.local_path = str(path)
        report.file_name = path.name
        report.file_size = path.stat().st_size
        report.sha256 = sha256_file(path)
        report.downloaded_at = datetime.utcnow()
        report.download_status = DownloadStatus.DOWNLOADED

        try:
            doc = fitz.open(str(path))
            report.pdf_pages = len(doc)
            doc.close()
        except Exception:
            pass

    def download_batch(
        self,
        reports: list[ReportRecord],
        dry_run: bool = False,
    ) -> list[ReportRecord]:
        """Download all reports in a list, returning updated records."""
        for report in reports:
            self.download(report, dry_run=dry_run)
        return reports
