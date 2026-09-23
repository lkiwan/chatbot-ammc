"""
Table analysis: detects financial tables in pdfplumber page output,
extracts (metric, year, value) tuples.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from extraction.normalizer import detect_unit, parse_value_with_unit, ParsedValue
from extraction.vocabulary import (
    detect_statement_type, normalize_metric_name, classify_metric
)


@dataclass
class MetricCell:
    metric_name: str
    normalized_name: str
    metric_category: str
    statement_type: str
    year: int
    raw_value: str
    parsed: ParsedValue
    page: int
    col_index: int
    row_index: int


@dataclass
class TableAnalysisResult:
    statement_type: Optional[str]
    unit: Optional[str]
    multiplier: float
    metrics: list[MetricCell] = field(default_factory=list)
    year_columns: dict[int, int] = field(default_factory=dict)  # col_idx → year
    confidence: float = 0.5

    @property
    def years_found(self) -> list[int]:
        return sorted(set(m.year for m in self.metrics), reverse=True)


_YEAR_RE = re.compile(r"\b(20\d{2}|19\d{2})\b")
_MIN_ROWS_FOR_FINANCIAL = 3


def _extract_years_from_headers(row: list[str]) -> dict[int, int]:
    """Return {column_index: year} for columns containing a year."""
    result: dict[int, int] = {}
    for i, cell in enumerate(row):
        m = _YEAR_RE.search(str(cell or ""))
        if m:
            result[i] = int(m.group(1))
    return result


def _clean_cell(cell: str | None) -> str:
    if cell is None:
        return ""
    return " ".join(str(cell).split()).strip()


def analyze_table(
    rows: list[list[str | None]],
    page: int,
    context_unit: str | None = None,
) -> TableAnalysisResult:
    """Analyze a pdfplumber table and extract financial metrics.

    Args:
        rows:          Table rows as returned by pdfplumber (list of lists).
        page:          Page number (1-based) where this table appears.
        context_unit:  Unit detected from page header or table caption.
    """
    if not rows or len(rows) < _MIN_ROWS_FOR_FINANCIAL:
        return TableAnalysisResult(statement_type=None, unit=None, multiplier=1.0)

    # Step 1: Find header rows (containing years)
    year_cols: dict[int, int] = {}
    header_row_idx = -1
    for i, row in enumerate(rows[:5]):  # look only in first 5 rows
        cleaned = [_clean_cell(c) for c in row]
        detected = _extract_years_from_headers(cleaned)
        if detected:
            year_cols = detected
            header_row_idx = i
            break

    if not year_cols:
        return TableAnalysisResult(statement_type=None, unit=None, multiplier=1.0)

    # Step 2: Detect unit from header row or table title
    table_unit = context_unit
    table_multiplier = 1.0
    if header_row_idx >= 0:
        header_text = " ".join(_clean_cell(c) for c in rows[header_row_idx])
        detected_unit, detected_mult = detect_unit(header_text)
        if detected_unit:
            table_unit = detected_unit
            table_multiplier = detected_mult
    # Also scan first 2 rows for unit
    if table_unit is None:
        for row in rows[:3]:
            row_text = " ".join(_clean_cell(c) for c in row)
            u, m = detect_unit(row_text)
            if u:
                table_unit = u
                table_multiplier = m
                break

    # Step 3: Collect row labels and detect statement type
    label_col = 0  # assume first column is label
    all_labels = [_clean_cell(rows[i][label_col]) for i in range(len(rows))
                  if rows[i] and _clean_cell(rows[i][label_col])]

    stmt_type = detect_statement_type(all_labels)

    # Step 4: Extract metric rows
    metrics: list[MetricCell] = []
    data_rows = rows[header_row_idx + 1:] if header_row_idx >= 0 else rows

    for row_i, row in enumerate(data_rows):
        if not row:
            continue

        label = _clean_cell(row[label_col]) if len(row) > label_col else ""
        if not label or len(label) < 2:
            continue

        norm_name = normalize_metric_name(label)
        if norm_name is None:
            continue

        cat, stmt = classify_metric(norm_name)
        if stmt_type and stmt != stmt_type and stmt not in ("other",):
            # Allow override if statement type not yet determined
            pass

        for col_i, year in year_cols.items():
            if col_i >= len(row):
                continue
            raw_val = _clean_cell(row[col_i])
            if not raw_val:
                continue

            pv = parse_value_with_unit(raw_val, context_unit=table_unit)
            if pv.value is None:
                continue

            # Override unit/multiplier from table context
            if pv.unit is None and table_unit:
                pv.unit = table_unit
                pv.multiplier = table_multiplier
            elif pv.unit == table_unit:
                pv.multiplier = table_multiplier

            metrics.append(MetricCell(
                metric_name=label,
                normalized_name=norm_name,
                metric_category=cat,
                statement_type=stmt,
                year=year,
                raw_value=raw_val,
                parsed=pv,
                page=page,
                col_index=col_i,
                row_index=header_row_idx + 1 + row_i,
            ))

    # Confidence: based on how many metrics found and whether years were detected
    confidence = 0.0
    if year_cols:
        confidence += 0.4
    if metrics:
        confidence += min(0.6, len(metrics) * 0.05)
    if table_unit:
        confidence += 0.1
    confidence = min(1.0, confidence)

    return TableAnalysisResult(
        statement_type=stmt_type,
        unit=table_unit,
        multiplier=table_multiplier,
        metrics=metrics,
        year_columns=year_cols,
        confidence=confidence,
    )
