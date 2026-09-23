"""Confidence scoring for extracted financial metrics."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ConfidenceFactors:
    has_clear_label: bool = False
    has_year: bool = False
    has_unit: bool = False
    from_table: bool = False
    value_plausible: bool = False
    no_footnote_conflict: bool = True
    consistent_with_context: bool = True

    # Weights for each factor
    _WEIGHTS = {
        "has_clear_label":         0.25,
        "has_year":                0.20,
        "has_unit":                0.15,
        "from_table":              0.15,
        "value_plausible":         0.15,
        "no_footnote_conflict":    0.05,
        "consistent_with_context": 0.05,
    }

    def score(self) -> float:
        total = sum(
            self._WEIGHTS[k] * int(getattr(self, k))
            for k in self._WEIGHTS
        )
        return round(min(1.0, max(0.0, total)), 4)


def calculate_confidence(
    metric_name: Optional[str],
    year: Optional[int],
    value: Optional[float],
    unit: Optional[str],
    from_table: bool,
    source_text: Optional[str] = None,
) -> float:
    """Compute a confidence score [0–1] for an extracted metric.

    Higher = more trustworthy.
    """
    factors = ConfidenceFactors(
        has_clear_label=bool(metric_name and len(metric_name) >= 3),
        has_year=year is not None and 1990 <= year <= 2030,
        has_unit=unit is not None,
        from_table=from_table,
        value_plausible=_is_plausible(value),
        no_footnote_conflict=True,
        consistent_with_context=True,
    )
    return factors.score()


def _is_plausible(value: Optional[float]) -> bool:
    """Basic plausibility check for a financial value."""
    if value is None:
        return False
    # Reject extreme outliers that are likely parsing errors
    if abs(value) > 1e15:
        return False
    # A value of exactly 0 is allowed (can be zero net income, etc.)
    return True
