"""
Main financial extraction engine.

Orchestrates: PDF loading → table analysis → metric extraction
→ normalization → validation → structured output.
"""
from __future__ import annotations

import hashlib
import logging
import re
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pdfplumber

from extraction.confidence import calculate_confidence
from extraction.normalizer import detect_unit, parse_value_with_unit
from extraction.ocr_detector import needs_ocr
from extraction.table_analyzer import MetricCell, analyze_table
from extraction.validator import (
    validate_balance_sheet, validate_income_statement,
    validate_year,
)
from extraction.vocabulary import normalize_metric_name

logger = logging.getLogger(__name__)


# ── Result types ──────────────────────────────────────────────────────────────

@dataclass
class ExtractedMetric:
    metric_name: str
    normalized_name: str
    metric_category: str
    statement_type: str
    year: int
    raw_value: str
    value: Optional[float]
    unit: Optional[str]
    currency: str = "MAD"
    source_page: Optional[int] = None
    source_section: Optional[str] = None
    source_text: Optional[str] = None
    confidence: float = 0.5
    extraction_method: str = "table"
    validation_warning: Optional[str] = None


@dataclass
class ExtractedStatement:
    statement_type: str    # income_statement | balance_sheet | cash_flow
    year: int
    unit: Optional[str]
    currency: str = "MAD"
    source_page: Optional[int] = None
    confidence: float = 0.5
    fields: dict[str, Optional[float]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


@dataclass
class ExtractionResult:
    pdf_path: str
    file_hash: str
    page_count: int
    ocr_required: bool
    ocr_reason: str
    extraction_status: str    # completed | partial | failed | ocr_required
    metrics: list[ExtractedMetric] = field(default_factory=list)
    statements: dict[str, ExtractedStatement] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    extraction_quality: float = 0.0

    @property
    def n_metrics(self) -> int:
        return len(self.metrics)

    @property
    def years_covered(self) -> list[int]:
        return sorted({m.year for m in self.metrics}, reverse=True)


# ── Extractor ─────────────────────────────────────────────────────────────────

class FinancialExtractor:
    """Extract structured financial data from a PDF annual report."""

    def __init__(
        self,
        confidence_threshold: float = 0.3,
        debug: bool = False,
    ) -> None:
        self.confidence_threshold = confidence_threshold
        self.debug = debug

    def extract(self, pdf_path: Path) -> ExtractionResult:
        """Run full extraction pipeline on a PDF.

        Returns an ExtractionResult regardless of success/failure.
        """
        start = time.time()
        path_str = str(pdf_path)

        file_hash = self._hash_file(pdf_path)
        if not pdf_path.exists():
            return ExtractionResult(
                pdf_path=path_str,
                file_hash="",
                page_count=0,
                ocr_required=False,
                ocr_reason="File not found",
                extraction_status="failed",
                errors=["File not found"],
            )

        # OCR detection
        ocr_req, ocr_reason = needs_ocr(pdf_path)
        if ocr_req:
            logger.warning("OCR required for %s: %s", pdf_path.name, ocr_reason)
            return ExtractionResult(
                pdf_path=path_str,
                file_hash=file_hash,
                page_count=0,
                ocr_required=True,
                ocr_reason=ocr_reason,
                extraction_status="ocr_required",
            )

        metrics: list[ExtractedMetric] = []
        errors: list[str] = []
        page_count = 0

        try:
            with pdfplumber.open(pdf_path) as pdf:
                page_count = len(pdf.pages)
                logger.info("Extracting %s (%d pages)", pdf_path.name, page_count)

                for page_idx, page in enumerate(pdf.pages, start=1):
                    try:
                        page_metrics = self._process_page(page, page_idx)
                        metrics.extend(page_metrics)
                    except Exception as exc:
                        msg = f"Page {page_idx}: {type(exc).__name__}: {exc}"
                        logger.debug(msg)
                        errors.append(msg)

        except Exception as exc:
            logger.error("Failed to open %s: %s", pdf_path.name, exc)
            return ExtractionResult(
                pdf_path=path_str,
                file_hash=file_hash,
                page_count=page_count,
                ocr_required=False,
                ocr_reason="",
                extraction_status="failed",
                errors=[f"{type(exc).__name__}: {exc}"],
            )

        # Deduplicate: keep highest-confidence metric per (normalized_name, year)
        metrics = self._deduplicate(metrics)

        # Build structured statements
        statements = self._build_statements(metrics)

        # Quality score
        quality = self._compute_quality(metrics, page_count)

        status = "completed"
        if not metrics:
            status = "partial" if not errors else "failed"
        elif errors:
            status = "partial"

        duration = time.time() - start
        logger.info(
            "Extracted %d metrics from %s in %.1fs (quality=%.2f)",
            len(metrics), pdf_path.name, duration, quality
        )

        return ExtractionResult(
            pdf_path=path_str,
            file_hash=file_hash,
            page_count=page_count,
            ocr_required=False,
            ocr_reason="",
            extraction_status=status,
            metrics=metrics,
            statements=statements,
            errors=errors,
            duration_seconds=duration,
            extraction_quality=quality,
        )

    # ── Private helpers ───────────────────────────────────────────────────

    def _process_page(self, page, page_idx: int) -> list[ExtractedMetric]:
        """Extract financial metrics from one PDF page."""
        results: list[ExtractedMetric] = []

        # Detect page-level unit from header text (first 200 chars)
        page_text = page.extract_text() or ""
        header_text = page_text[:300]
        context_unit, _ = detect_unit(header_text)

        tables = page.extract_tables()
        if not tables:
            return results

        for table in tables:
            if not table or len(table) < 2:
                continue

            analysis = analyze_table(table, page=page_idx, context_unit=context_unit)
            if not analysis.metrics:
                continue

            for cell in analysis.metrics:
                if cell.parsed.value is None:
                    continue

                conf = calculate_confidence(
                    metric_name=cell.normalized_name,
                    year=cell.year,
                    value=cell.parsed.value,
                    unit=cell.parsed.unit,
                    from_table=True,
                )

                if conf < self.confidence_threshold:
                    if self.debug:
                        logger.debug(
                            "Skipping low-confidence: %s %d = %s (conf=%.2f)",
                            cell.normalized_name, cell.year, cell.raw_value, conf
                        )
                    continue

                # Source context: first 200 chars of page text as context
                source_snippet = page_text[:200].replace("\n", " ") if page_text else None

                results.append(ExtractedMetric(
                    metric_name=cell.metric_name,
                    normalized_name=cell.normalized_name,
                    metric_category=cell.metric_category,
                    statement_type=cell.statement_type,
                    year=cell.year,
                    raw_value=cell.raw_value,
                    value=cell.parsed.value,
                    unit=cell.parsed.unit or analysis.unit,
                    currency="MAD",
                    source_page=page_idx,
                    source_text=source_snippet,
                    confidence=conf,
                    extraction_method="table",
                ))

        return results

    def _deduplicate(self, metrics: list[ExtractedMetric]) -> list[ExtractedMetric]:
        """Keep highest-confidence metric per (normalized_name, year, statement_type)."""
        best: dict[tuple[str, int, str], ExtractedMetric] = {}
        for m in metrics:
            key = (m.normalized_name, m.year, m.statement_type)
            existing = best.get(key)
            if existing is None or m.confidence > existing.confidence:
                best[key] = m
        return list(best.values())

    def _build_statements(
        self, metrics: list[ExtractedMetric]
    ) -> dict[str, ExtractedStatement]:
        """Group metrics into structured financial statements."""
        statements: dict[str, ExtractedStatement] = {}

        # Group by (statement_type, year)
        groups: dict[tuple[str, int], list[ExtractedMetric]] = {}
        for m in metrics:
            key = (m.statement_type, m.year)
            groups.setdefault(key, []).append(m)

        # Map normalized_name → statement field name
        _FIELD_MAP = {
            # Income statement
            "revenue":               "revenue",
            "net_banking_income":    "net_banking_income",
            "gross_profit":          "gross_profit",
            "operating_income":      "operating_income",
            "ebitda":                "ebitda",
            "finance_result":        "finance_result",
            "profit_before_tax":     "profit_before_tax",
            "income_tax":            "income_tax",
            "net_income":            "net_income",
            "net_income_group_share":"net_income_group_share",
            "minority_interests":    "minority_interests",
            # Balance sheet
            "total_assets":          "total_assets",
            "current_assets":        "current_assets",
            "non_current_assets":    "non_current_assets",
            "cash":                  "cash",
            "receivables":           "receivables",
            "inventory":             "inventory",
            "total_liabilities":     "total_liabilities",
            "current_liabilities":   "current_liabilities",
            "non_current_liabilities":"non_current_liabilities",
            "debt":                  "debt",
            "equity":                "equity",
            # Cash flow
            "operating_cash_flow":   "operating_cash_flow",
            "investing_cash_flow":   "investing_cash_flow",
            "financing_cash_flow":   "financing_cash_flow",
            "capex":                 "capex",
            "free_cash_flow":        "free_cash_flow",
            "net_change_in_cash":    "net_change_in_cash",
        }

        for (stmt_type, year), group in groups.items():
            key = f"{stmt_type}_{year}"
            unit = next((m.unit for m in group if m.unit), None)
            avg_conf = sum(m.confidence for m in group) / len(group)
            source_page = min((m.source_page for m in group if m.source_page), default=None)

            fields: dict[str, Optional[float]] = {}
            for m in group:
                field_name = _FIELD_MAP.get(m.normalized_name)
                if field_name:
                    fields[field_name] = m.value

            stmt = ExtractedStatement(
                statement_type=stmt_type,
                year=year,
                unit=unit,
                source_page=source_page,
                confidence=avg_conf,
                fields=fields,
            )

            # Validation
            if stmt_type == "balance_sheet":
                val = validate_balance_sheet(
                    fields.get("total_assets"),
                    fields.get("total_liabilities"),
                    fields.get("equity"),
                )
                stmt.warnings = val.warnings

            elif stmt_type == "income_statement":
                val = validate_income_statement(
                    fields.get("revenue") or fields.get("net_banking_income"),
                    fields.get("net_income"),
                    fields.get("gross_profit"),
                )
                stmt.warnings = val.warnings

            statements[key] = stmt

        return statements

    def _compute_quality(self, metrics: list[ExtractedMetric], page_count: int) -> float:
        """Compute overall extraction quality score [0-1]."""
        if not metrics:
            return 0.0
        avg_conf = sum(m.confidence for m in metrics) / len(metrics)
        n_distinct = len({m.normalized_name for m in metrics})
        coverage = min(1.0, n_distinct / 10)   # 10 distinct metrics → full coverage
        return round((avg_conf * 0.6 + coverage * 0.4), 4)

    @staticmethod
    def _hash_file(path: Path) -> str:
        if not path.exists():
            return ""
        sha = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha.update(chunk)
        return sha.hexdigest()
