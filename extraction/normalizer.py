"""
Financial number and unit normalization for Moroccan financial reports.

Handles French numeric conventions, parenthetical negatives, and MAD units.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# ── Unit registry ─────────────────────────────────────────────────────────────

# Maps variant → (canonical_unit, multiplier_to_MAD)
# multiplier_to_MAD: multiply value by this to get MAD
_UNIT_REGISTRY: dict[str, tuple[str, float]] = {
    # MAD / DH
    "mad":    ("MAD",   1.0),
    "dh":     ("MAD",   1.0),
    "dhs":    ("MAD",   1.0),
    "dirham": ("MAD",   1.0),
    "dirhams": ("MAD",  1.0),
    # Thousands
    "kdh":    ("KMAD",  1_000.0),
    "kmad":   ("KMAD",  1_000.0),
    "k mad":  ("KMAD",  1_000.0),
    "k dh":   ("KMAD",  1_000.0),
    "millier": ("KMAD", 1_000.0),
    "milliers": ("KMAD",1_000.0),
    "milliers de dirhams": ("KMAD", 1_000.0),
    "milliers de mad": ("KMAD", 1_000.0),
    "kmdh":   ("KMAD",  1_000.0),
    "k.dh":   ("KMAD",  1_000.0),
    # Millions
    "mdh":    ("MMAD",  1_000_000.0),
    "mmad":   ("MMAD",  1_000_000.0),
    "m mad":  ("MMAD",  1_000_000.0),
    "m dh":   ("MMAD",  1_000_000.0),
    "m.dh":   ("MMAD",  1_000_000.0),
    "mmdh":   ("MMAD",  1_000_000.0),
    "million": ("MMAD", 1_000_000.0),
    "millions": ("MMAD",1_000_000.0),
    "millions de dirhams": ("MMAD", 1_000_000.0),
    "millions de mad": ("MMAD",     1_000_000.0),
    "millions mad": ("MMAD",        1_000_000.0),
    "mio":    ("MMAD",  1_000_000.0),
    "mio dh": ("MMAD",  1_000_000.0),
    # Billions
    "bmdh":   ("BMMAD", 1_000_000_000.0),
    "milliard": ("BMMAD", 1_000_000_000.0),
    "milliards": ("BMMAD",1_000_000_000.0),
    "milliards de dirhams": ("BMMAD", 1_000_000_000.0),
    "milliards de mad": ("BMMAD",     1_000_000_000.0),
    "md":     ("BMMAD", 1_000_000_000.0),
    # Percentages — not a MAD unit, handled separately
    "%":      ("%",     1.0),
    "pct":    ("%",     1.0),
    "pc":     ("%",     1.0),
}

# Sorted by length descending for greedy matching
_UNIT_PATTERNS = sorted(_UNIT_REGISTRY.keys(), key=len, reverse=True)


@dataclass
class ParsedValue:
    raw_text: str
    value: Optional[float]
    unit: Optional[str]       # canonical unit (MMAD, KMAD, MAD, %)
    multiplier: float         # to convert value → base MAD (1.0 if unit=MAD or %)
    is_negative: bool
    is_percentage: bool
    confidence: float = 1.0
    notes: list[str] = field(default_factory=list)

    @property
    def value_in_mad(self) -> Optional[float]:
        if self.value is None or self.is_percentage:
            return None
        return self.value * self.multiplier


def detect_unit(text: str) -> tuple[str | None, float]:
    """Detect the financial unit in a text fragment.

    Returns (canonical_unit, multiplier_to_MAD) or (None, 1.0).
    """
    normalized = " ".join(text.lower().split())
    for pat in _UNIT_PATTERNS:
        if pat in normalized:
            canonical, multiplier = _UNIT_REGISTRY[pat]
            return canonical, multiplier
    return None, 1.0


def parse_number(text: str) -> Optional[float]:
    """Parse a French-formatted financial number to float.

    Handles:
      "1 245"        → 1245.0
      "1 245,50"     → 1245.50
      "1.245,50"     → 1245.50
      "1.245.500"    → 1245500.0
      "(125)"        → -125.0
      "-125"         → -125.0
      "125 %"        → 12.5  (stored as-is, caller checks is_percentage)
      "N/A", "—"     → None
      ""             → None
    """
    if not text:
        return None

    original = text
    text = text.strip()

    # Reject non-numeric placeholders
    _NULLISH = {"n/a", "na", "—", "-", "–", "néant", "nd", "ns", "/", "...", "nc", "non communiqué"}
    if text.lower() in _NULLISH:
        return None

    # Strip surrounding whitespace and footnote markers (e.g. "1 245 (1)")
    text = re.sub(r"\s*\([^)0-9-]+\)\s*$", "", text)   # remove "(note)" at end
    text = re.sub(r"\*+\s*$", "", text)                  # remove trailing *
    text = text.strip()

    # Handle parenthetical negatives: "(1 245)" → -1245
    negative_parens = False
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1].strip()
        negative_parens = True

    # Handle explicit minus
    negative_sign = text.startswith("-")
    if negative_sign:
        text = text[1:].strip()

    # Strip trailing unit text (MDH etc.)
    text = re.sub(
        r"(?i)\s*(milliards?|millions?|milliers?|mdh|mmad|kdh|kmad|mad|dh|%|pct|mio)\s*$",
        "", text
    ).strip()

    if not text:
        return None

    # Now we have a bare number possibly with French formatting
    # Determine thousands separator vs decimal separator:
    # French: "1 245,50" or "1.245,50" (dot = thousands, comma = decimal)
    # International: "1,245.50" (comma = thousands, dot = decimal)

    # Count dots and commas
    n_dots = text.count(".")
    n_commas = text.count(",")

    try:
        if n_commas == 1 and n_dots == 0:
            # "1 245,50" or "1245,50" — comma is decimal
            text = text.replace(" ", "").replace(",", ".")
        elif n_dots >= 1 and n_commas == 1:
            # "1.245,50" or "1.245.500" with comma
            # Comma is decimal, dots are thousands
            text = text.replace(" ", "").replace(".", "").replace(",", ".")
        elif n_dots >= 2 and n_commas == 0:
            # "1.245.500" — dots are thousands
            text = text.replace(" ", "").replace(".", "")
        elif n_dots == 1 and n_commas == 0:
            # "1245.50" — dot is decimal
            text = text.replace(" ", "")
        else:
            # Spaces only as thousands separators, or no separator
            text = text.replace(" ", "").replace(",", "")

        value = float(text)
    except ValueError:
        return None

    if negative_parens or negative_sign:
        value = -abs(value)

    return value


def parse_unit(text: str) -> tuple[str | None, float]:
    """Extract unit from a cell or header text. Returns (unit, multiplier)."""
    return detect_unit(text)


def parse_value_with_unit(text: str, context_unit: str | None = None) -> ParsedValue:
    """Full parse of a financial cell: value + unit + sign + confidence.

    Args:
        text: Raw cell text (e.g. "1 245,50 MDH", "(125)", "12,5 %")
        context_unit: Unit inferred from table header (e.g. "MMAD")
    """
    raw = text.strip()
    is_negative = False
    is_percentage = "%" in text or re.search(r"\bpct\b|\bpc\b", text, re.I) is not None

    # Detect inline unit
    unit, multiplier = detect_unit(raw)

    # Fall back to context unit
    if unit is None and context_unit:
        cu = context_unit.lower().strip()
        unit, multiplier = _UNIT_REGISTRY.get(cu, (context_unit, 1.0))

    if is_percentage:
        unit = "%"
        multiplier = 1.0

    value = parse_number(raw)
    if value is not None and value < 0:
        is_negative = True

    # Confidence: higher if we found explicit unit or value is clean
    confidence = 1.0
    if value is None:
        confidence = 0.0
    elif unit is None:
        confidence = 0.7

    return ParsedValue(
        raw_text=raw,
        value=value,
        unit=unit,
        multiplier=multiplier,
        is_negative=is_negative,
        is_percentage=is_percentage,
        confidence=confidence,
    )
