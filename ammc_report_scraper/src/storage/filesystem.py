"""Filesystem helpers: directory creation and file management."""
from __future__ import annotations

from pathlib import Path

from src.config import PATHS


def ensure_project_dirs() -> None:
    PATHS.ensure_dirs()


def company_reports_dir(sector: str, company_name: str) -> Path:
    from src.utils.normalization import sanitize_filename
    sector_dir = sanitize_filename(sector) if sector else "UNKNOWN_SECTOR"
    company_dir = sanitize_filename(company_name)
    path = PATHS.reports_dir / sector_dir / company_dir
    path.mkdir(parents=True, exist_ok=True)
    return path
