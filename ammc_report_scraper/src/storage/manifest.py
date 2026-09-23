"""Manifest manager: read/write CSV tracking all reports."""
from __future__ import annotations

import csv
import logging
from pathlib import Path

import pandas as pd

from src.config import PATHS
from src.parsers.report_parser import DownloadStatus, ReportRecord

logger = logging.getLogger(__name__)

_MANIFEST_PATH = PATHS.manifests_dir / "reports_manifest.csv"
_COMPANIES_PATH = PATHS.companies_dir / "companies.csv"

_MANIFEST_COLS = [
    "report_id", "company_id", "company_name", "company_name_normalized",
    "sector", "year", "document_type", "title", "source_url", "document_url",
    "local_path", "file_name", "file_size", "sha256", "download_status",
    "pdf_pages", "scraped_at", "downloaded_at", "error",
]

_COMPANIES_COLS = [
    "company_id", "company_name", "company_name_normalized",
    "sector", "sector_normalized", "ammc_url", "website", "scraped_at",
]


class ManifestManager:
    """Read/write manifest CSV and companies CSV."""

    def __init__(self) -> None:
        PATHS.manifests_dir.mkdir(parents=True, exist_ok=True)
        PATHS.companies_dir.mkdir(parents=True, exist_ok=True)
        self._manifest_path = _MANIFEST_PATH
        self._companies_path = _COMPANIES_PATH

    # ─── Companies ──────────────────────────────────────────────────────────

    def save_companies(self, records: list) -> None:
        """Write companies to CSV (overwrite)."""
        rows = [r.to_csv_row() for r in records]
        df = pd.DataFrame(rows, columns=_COMPANIES_COLS)
        df.to_csv(self._companies_path, index=False, encoding="utf-8-sig")
        logger.info("Saved %d companies to %s", len(rows), self._companies_path)

    def load_companies(self) -> pd.DataFrame:
        if not self._companies_path.exists():
            return pd.DataFrame(columns=_COMPANIES_COLS)
        return pd.read_csv(self._companies_path, dtype=str, encoding="utf-8-sig")

    # ─── Manifest ───────────────────────────────────────────────────────────

    def load_manifest(self) -> pd.DataFrame:
        if not self._manifest_path.exists():
            return pd.DataFrame(columns=_MANIFEST_COLS)
        return pd.read_csv(self._manifest_path, dtype=str, encoding="utf-8-sig")

    def is_already_downloaded(self, report_id: str) -> bool:
        """
        Return True if this report has been successfully downloaded.
        Checks manifest status AND that the local file still exists and is valid.
        """
        from pathlib import Path
        from src.downloaders.pdf_downloader import PDFDownloader

        df = self.load_manifest()
        if df.empty:
            return False

        # Accept both "downloaded" and "skipped" as evidence of prior success
        done_statuses = {DownloadStatus.DOWNLOADED.value, DownloadStatus.SKIPPED.value}
        mask = (df["report_id"] == report_id) & df["download_status"].isin(done_statuses)
        if not mask.any():
            return False

        # Also verify the physical file still exists and is valid
        row = df[mask].iloc[0]
        local_path = row.get("local_path", "")
        if local_path and Path(local_path).exists():
            err = PDFDownloader._validate_pdf(Path(local_path))
            if err is None:
                return True  # File is valid
            # File exists but is corrupt - re-download
            Path(local_path).unlink(missing_ok=True)
            return False

        # Path not recorded or file missing - need to re-download
        return False

    def upsert_report(self, report: ReportRecord) -> None:
        """Insert or update one report in the manifest CSV."""
        df = self.load_manifest()
        # Ensure all values are strings for consistent dtype handling
        row = {k: str(v) if v is not None else "" for k, v in report.to_csv_row().items()}

        if not df.empty and report.report_id in df["report_id"].values:
            idx = df.index[df["report_id"] == report.report_id][0]
            for col, val in row.items():
                if col in df.columns:
                    df.at[idx, col] = val
        else:
            new_row = pd.DataFrame([row])
            df = pd.concat([df, new_row], ignore_index=True)

        df.to_csv(self._manifest_path, index=False, encoding="utf-8-sig")

    def upsert_reports(self, reports: list[ReportRecord]) -> None:
        """Batch upsert multiple reports."""
        df = self.load_manifest()
        rows = [r.to_csv_row() for r in reports]
        new_df = pd.DataFrame(rows, columns=_MANIFEST_COLS)

        if df.empty:
            df = new_df
        else:
            # Drop existing rows that will be updated
            ids_to_update = {r.report_id for r in reports}
            df = df[~df["report_id"].isin(ids_to_update)]
            df = pd.concat([df, new_df], ignore_index=True)

        df.to_csv(self._manifest_path, index=False, encoding="utf-8-sig")
        logger.info("Manifest updated: %d total records", len(df))

    def summary(self) -> dict:
        """Return download statistics from the manifest."""
        df = self.load_manifest()
        if df.empty:
            return {"total": 0}
        counts = df["download_status"].value_counts().to_dict()
        return {
            "total": len(df),
            "downloaded": counts.get(DownloadStatus.DOWNLOADED.value, 0),
            "skipped": counts.get(DownloadStatus.SKIPPED.value, 0),
            "failed": counts.get(DownloadStatus.FAILED.value, 0),
            "invalid_pdf": counts.get(DownloadStatus.INVALID_PDF.value, 0),
            "pending": counts.get(DownloadStatus.PENDING.value, 0),
        }
