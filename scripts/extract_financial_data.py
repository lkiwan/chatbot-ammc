"""
Run FinancialExtractor on all PDFs and persist results to PostgreSQL.

Idempotent: skips reports already extracted (status=completed).
Run: python scripts/extract_financial_data.py [--force] [--company SLUG] [--limit N]
"""
from __future__ import annotations

import argparse
import logging
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional



sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import EXTRACTION_CONFIDENCE_THRESHOLD, EXTRACTION_DEBUG
from db.models import (
    BalanceSheet, CashFlow, Company, ExtractionError,
    FinancialMetric, IncomeStatement, Report,
)
from db.session import check_connection, get_db
from extraction.financial_extractor import ExtractionResult, FinancialExtractor

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def persist_result(db, report: Report, result: ExtractionResult) -> None:
    """Write extracted data to PostgreSQL (metrics + statements)."""

    # Update report status
    report.extraction_status  = result.extraction_status
    report.extraction_quality = result.extraction_quality
    if result.file_hash and not report.file_hash:
        report.file_hash = result.file_hash
    if result.page_count and not report.page_count:
        report.page_count = result.page_count

    company_id = report.company_id

    # ── Financial metrics ─────────────────────────────────────────────────────
    for m in result.metrics:
        existing = (
            db.query(FinancialMetric)
            .filter_by(
                report_id              = report.id,
                normalized_metric_name = m.normalized_name,
                year                   = m.year,
                statement_type         = m.statement_type,
            )
            .first()
        )
        if existing:
            if m.confidence > existing.confidence:
                existing.raw_value         = m.raw_value
                existing.value             = m.value
                existing.unit              = m.unit
                existing.confidence        = m.confidence
                existing.validation_warning = m.validation_warning
            continue

        db.add(FinancialMetric(
            company_id             = company_id,
            report_id              = report.id,
            year                   = m.year,
            metric_name            = m.metric_name,
            normalized_metric_name = m.normalized_name,
            metric_category        = m.metric_category,
            statement_type         = m.statement_type,
            raw_value              = m.raw_value,
            value                  = m.value,
            unit                   = m.unit,
            currency               = m.currency,
            source_page            = m.source_page,
            source_text            = m.source_text,
            confidence             = m.confidence,
            extraction_method      = m.extraction_method,
            validation_warning     = m.validation_warning,
        ))

    # ── Structured statements ─────────────────────────────────────────────────
    for key, stmt in result.statements.items():
        year = stmt.year
        f    = stmt.fields

        if stmt.statement_type == "income_statement":
            existing = db.query(IncomeStatement).filter_by(
                company_id=company_id, report_id=report.id, year=year
            ).first()
            if not existing:
                db.add(IncomeStatement(
                    company_id             = company_id,
                    report_id              = report.id,
                    year                   = year,
                    revenue                = f.get("revenue"),
                    net_banking_income     = f.get("net_banking_income"),
                    gross_profit           = f.get("gross_profit"),
                    operating_income       = f.get("operating_income"),
                    ebitda                 = f.get("ebitda"),
                    finance_result         = f.get("finance_result"),
                    profit_before_tax      = f.get("profit_before_tax"),
                    income_tax             = f.get("income_tax"),
                    net_income             = f.get("net_income"),
                    net_income_group_share = f.get("net_income_group_share"),
                    minority_interests     = f.get("minority_interests"),
                    currency               = stmt.currency,
                    unit                   = stmt.unit,
                    source_page            = stmt.source_page,
                    confidence             = stmt.confidence,
                ))

        elif stmt.statement_type == "balance_sheet":
            existing = db.query(BalanceSheet).filter_by(
                company_id=company_id, report_id=report.id, year=year
            ).first()
            if not existing:
                from extraction.validator import validate_balance_sheet
                val = validate_balance_sheet(
                    f.get("total_assets"),
                    f.get("total_liabilities"),
                    f.get("equity"),
                )
                db.add(BalanceSheet(
                    company_id               = company_id,
                    report_id                = report.id,
                    year                     = year,
                    total_assets             = f.get("total_assets"),
                    current_assets           = f.get("current_assets"),
                    non_current_assets       = f.get("non_current_assets"),
                    cash                     = f.get("cash"),
                    receivables              = f.get("receivables"),
                    inventory                = f.get("inventory"),
                    total_liabilities        = f.get("total_liabilities"),
                    current_liabilities      = f.get("current_liabilities"),
                    non_current_liabilities  = f.get("non_current_liabilities"),
                    debt                     = f.get("debt"),
                    equity                   = f.get("equity"),
                    balance_check_passed     = val.passed,
                    balance_discrepancy_pct  = val.discrepancy_pct,
                    currency                 = stmt.currency,
                    unit                     = stmt.unit,
                    source_page              = stmt.source_page,
                    confidence               = stmt.confidence,
                ))

        elif stmt.statement_type == "cash_flow":
            existing = db.query(CashFlow).filter_by(
                company_id=company_id, report_id=report.id, year=year
            ).first()
            if not existing:
                db.add(CashFlow(
                    company_id           = company_id,
                    report_id            = report.id,
                    year                 = year,
                    operating_cash_flow  = f.get("operating_cash_flow"),
                    investing_cash_flow  = f.get("investing_cash_flow"),
                    financing_cash_flow  = f.get("financing_cash_flow"),
                    capex                = f.get("capex"),
                    free_cash_flow       = f.get("free_cash_flow"),
                    net_change_in_cash   = f.get("net_change_in_cash"),
                    currency             = stmt.currency,
                    unit                 = stmt.unit,
                    source_page          = stmt.source_page,
                    confidence           = stmt.confidence,
                ))


def run_extraction(
    force: bool = False,
    company_filter: Optional[str] = None,
    limit: Optional[int] = None,
) -> None:
    if not check_connection():
        logger.error("Cannot connect to PostgreSQL — is docker compose up?")
        sys.exit(1)

    extractor = FinancialExtractor(
        confidence_threshold=EXTRACTION_CONFIDENCE_THRESHOLD,
        debug=EXTRACTION_DEBUG,
    )

    with get_db() as db:
        q = db.query(Report)
        if not force:
            q = q.filter(Report.extraction_status.in_(["pending", "partial", "failed"]))
        if company_filter:
            q = q.join(Company).filter(Company.normalized_name == company_filter)
        if limit:
            q = q.limit(limit)
        reports = q.all()

    logger.info("Reports to process: %d", len(reports))

    job_started = datetime.now(timezone.utc)
    n_ok = n_fail = n_ocr = 0

    for i, report in enumerate(reports, 1):
        pdf_path = Path(report.pdf_path) if report.pdf_path else None

        if not pdf_path or not pdf_path.exists():
            logger.warning("[%d/%d] PDF not found: %s", i, len(reports), report.pdf_filename)
            with get_db() as db:
                r = db.query(Report).get(report.id)
                r.extraction_status = "failed"
            n_fail += 1
            continue

        logger.info("[%d/%d] Extracting: %s", i, len(reports), pdf_path.name)

        try:
            result = extractor.extract(pdf_path)

            with get_db() as db:
                r = db.query(Report).get(report.id)
                persist_result(db, r, result)

            if result.extraction_status == "ocr_required":
                n_ocr += 1
            elif result.extraction_status in ("completed", "partial"):
                n_ok += 1
                logger.info(
                    "  -> %d metrics, quality=%.2f, years=%s",
                    result.n_metrics, result.extraction_quality, result.years_covered,
                )
            else:
                n_fail += 1
                logger.warning("  -> failed: %s", result.errors)

        except Exception as exc:
            logger.error("Unhandled error for %s: %s", pdf_path.name, exc)
            with get_db() as db:
                db.add(ExtractionError(
                    report_id     = report.id,
                    filename      = pdf_path.name,
                    error_type    = type(exc).__name__,
                    error_message = str(exc),
                    stack_trace   = traceback.format_exc(),
                ))
                r = db.query(Report).get(report.id)
                r.extraction_status = "failed"
            n_fail += 1

    duration = (datetime.now(timezone.utc) - job_started).total_seconds()

    logger.info(
        "Extraction complete: ok=%d, ocr_required=%d, failed=%d in %.0fs",
        n_ok, n_ocr, n_fail, duration,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract financial data from PDFs → PostgreSQL")
    parser.add_argument("--force",   action="store_true",
                        help="Re-extract even already-completed reports")
    parser.add_argument("--company", metavar="SLUG",
                        help="Only process one company (normalized_name)")
    parser.add_argument("--limit",   type=int, metavar="N",
                        help="Process at most N reports")
    args = parser.parse_args()
    run_extraction(force=args.force, company_filter=args.company, limit=args.limit)


if __name__ == "__main__":
    main()
