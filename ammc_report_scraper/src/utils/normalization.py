"""Normalize company and sector names for deduplication."""
from __future__ import annotations

import re
import unicodedata


def _strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalize_company_name(name: str) -> str:
    """
    Normalize a company name for deduplication purposes.
    - Lowercase
    - Remove accents
    - Collapse whitespace/hyphens/underscores
    - Remove common legal suffixes
    """
    text = name.strip()
    text = _strip_accents(text)
    text = text.lower()
    # Replace hyphens, underscores, dots with spaces
    text = re.sub(r"[-_.]", " ", text)
    # Remove legal suffixes
    legal = r"\b(sa|sarl|sca|spa|sas|snc|sci|group|groupe|holding|bank|banque|maroc|morocco)\b"
    text = re.sub(legal, "", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_sector(sector: str) -> str:
    """Normalize sector name."""
    text = sector.strip()
    text = _strip_accents(text)
    text = text.lower()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def sanitize_filename(name: str) -> str:
    """
    Convert a string to a safe filesystem filename.
    Keeps alphanumerics, spaces (as underscores), and hyphens.
    """
    name = _strip_accents(name.strip())
    name = re.sub(r"[^\w\s\-]", "", name)
    name = re.sub(r"[\s]+", "_", name)
    name = re.sub(r"_+", "_", name)
    return name.strip("_").upper()
