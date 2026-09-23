"""Data models and parsing logic for AMMC financial reports."""
from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class DownloadStatus(str, Enum):
    PENDING = "pending"
    DOWNLOADED = "downloaded"
    SKIPPED = "skipped"
    FAILED = "failed"
    INVALID_PDF = "invalid_pdf"


class DocumentType(str, Enum):
    ANNUAL_REPORT = "Rapports annuels"
    SEMESTER_REPORT = "Rapports 1er semestre"
    OTHER = "Autre"


class ReportRecord(BaseModel):
    """One financial report document."""

    report_id: str = ""
    company_id: str
    company_name: str
    company_name_normalized: str
    sector: str
    year: int
    document_type: DocumentType = DocumentType.ANNUAL_REPORT
    title: str = ""
    source_url: str  # The document page URL (/fr/espace-emetteurs/etats-financiers/...)
    document_url: str = ""  # Direct PDF URL
    local_path: str = ""
    file_name: str = ""
    file_size: int = 0
    sha256: str = ""
    download_status: DownloadStatus = DownloadStatus.PENDING
    pdf_pages: int = 0
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    downloaded_at: Optional[datetime] = None
    error: str = ""

    def to_csv_row(self) -> dict:
        return {
            "report_id": self.report_id,
            "company_id": self.company_id,
            "company_name": self.company_name,
            "company_name_normalized": self.company_name_normalized,
            "sector": self.sector,
            "year": self.year,
            "document_type": self.document_type.value,
            "title": self.title,
            "source_url": self.source_url,
            "document_url": self.document_url,
            "local_path": self.local_path,
            "file_name": self.file_name,
            "file_size": self.file_size,
            "sha256": self.sha256,
            "download_status": self.download_status.value,
            "pdf_pages": self.pdf_pages,
            "scraped_at": self.scraped_at.isoformat(),
            "downloaded_at": self.downloaded_at.isoformat() if self.downloaded_at else "",
            "error": self.error,
        }


# ─── Detection helpers ──────────────────────────────────────────────────────

_ANNUAL_KEYWORDS = [
    r"rapport\s+annuel",
    r"rapports\s+annuels",
    r"rapport\s+financier\s+annuel",
    r"annual\s+report",
    r"-rfa-",
    r"\brfa\b",
]

_EXCLUDE_KEYWORDS = [
    r"semestriel",
    r"semestre",
    r"1er\s+semestre",
    r"premier\s+semestre",
    r"-rfs-",
    r"\brfs\b",
    r"communiqu",
    r"rapport\s+esg",
    r"rapport\s+de\s+gestion",
    r"états\s+financiers\s+semestriels",
]


def is_annual_report(text: str) -> bool:
    """Return True if text/URL identifies an annual report."""
    lower = text.lower()
    for pattern in _EXCLUDE_KEYWORDS:
        if re.search(pattern, lower):
            return False
    for pattern in _ANNUAL_KEYWORDS:
        if re.search(pattern, lower):
            return True
    return False


def extract_year_from_url(url: str) -> Optional[int]:
    """Extract a 4-digit year from a document URL or slug."""
    m = re.search(r"\b(20[12]\d)\b", url)
    return int(m.group(1)) if m else None


def extract_year_from_text(text: str) -> Optional[int]:
    """Extract a 4-digit year from arbitrary text."""
    m = re.search(r"\b(20[12]\d)\b", text)
    return int(m.group(1)) if m else None


def make_report_id(company_id: str, year: int) -> str:
    return f"{company_id}_{year}"
