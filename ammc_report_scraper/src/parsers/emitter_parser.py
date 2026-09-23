"""Data models and parsing logic for AMMC emitters."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class EmitterRecord(BaseModel):
    """One company/emitter from the AMMC emitters list."""

    company_id: str
    company_name: str
    company_name_original: str
    company_name_normalized: str
    sector: str
    sector_normalized: str
    ammc_url: str
    website: Optional[str] = None
    scraped_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("company_name", "company_name_original", mode="before")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return v.strip() if v else v

    def to_csv_row(self) -> dict:
        return {
            "company_id": self.company_id,
            "company_name": self.company_name_original,
            "company_name_normalized": self.company_name_normalized,
            "sector": self.sector,
            "sector_normalized": self.sector_normalized,
            "ammc_url": self.ammc_url,
            "website": self.website or "",
            "scraped_at": self.scraped_at.isoformat(),
        }


def extract_node_id(url: str) -> Optional[str]:
    """Extract numeric node ID from emitter list URL."""
    m = re.search(r"/liste-des-emetteurs/(\d+)", url)
    return m.group(1) if m else None


def extract_company_slug(url: str) -> Optional[str]:
    """Extract company slug from company profile URL like /fr/espace-emetteurs/attijariwafa-bank."""
    # Matches /fr/espace-emetteurs/{slug} but not subpaths like etats-financiers
    m = re.match(r".*/espace-emetteurs/([^/]+)$", url)
    if m:
        slug = m.group(1)
        # Exclude known non-company paths
        excluded = {"liste-des-emetteurs", "etats-financiers", "communiques-presse-emetteurs",
                    "documents-information"}
        if slug not in excluded and not slug.isdigit():
            return slug
    return None
