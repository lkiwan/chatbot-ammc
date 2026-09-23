"""
Validate extracted financial data quality across the database.

Prints a per-company/year quality summary. Does NOT modify any data.
Run: python scripts/validate_extraction.py [--company SLUG] [--year YYYY]
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, text

from db.models import BalanceSheet, Company, FinancialMetric, IncomeStatement, Report
from db.session import check_connection, get_db
from extraction.validator import validate_balance_sheet, validate_income_statement

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def validate_all(
    company_filter: Optional[str] = None,
    year_filter: Optional[int] = None,
) -> None:
    if not check_connection():
        logger.error("Cannot connect to PostgreSQL")
        sys.exit(1)

    issues_found = 0

    with get_db() as db:
        q = db.query(BalanceSheet).join(Company)
        if company_filter:
            q = q.filter(Company.normalized_name == company_filter)
        if year_filter:
            q = q.filter(BalanceSheet.year == year_filter)

        balance_sheets = q.all()
        logger.info("Validating %d balance sheets…", len(balance_sheets))

        for bs in balance_sheets:
            result = validate_balance_sheet(
                bs.total_assets,
                bs.total_liabilities,
                bs.equity,
            )
            if not result.passed:
                company_name = bs.company.name if bs.company else bs.company_id
                for w in result.warnings:
                    logger.warning("[BS] %s %d: %s", company_name, bs.year, w)
                    issues_found += 1
                if not bs.balance_check_passed:
                    pass  # already flagged in DB

        # ── Income statement checks ───────────────────────────────────────────
        q2 = db.query(IncomeStatement).join(Company)
        if company_filter:
            q2 = q2.filter(Company.normalized_name == company_filter)
        if year_filter:
            q2 = q2.filter(IncomeStatement.year == year_filter)

        income_stmts = q2.all()
        logger.info("Validating %d income statements…", len(income_stmts))

        for ist in income_stmts:
            revenue = ist.revenue or ist.net_banking_income
            result = validate_income_statement(revenue, ist.net_income, ist.gross_profit)
            if not result.passed:
                company_name = ist.company.name if ist.company else ist.company_id
                for w in result.warnings:
                    logger.warning("[IS] %s %d: %s", company_name, ist.year, w)
                    issues_found += 1

        # ── Low-confidence metrics ────────────────────────────────────────────
        low_conf = (
            db.query(FinancialMetric, Company.name)
            .join(Company)
            .filter(FinancialMetric.confidence < 0.4)
            .count()
        )
        if low_conf:
            logger.warning("Low-confidence metrics (< 0.4): %d rows", low_conf)

        # ── Summary ───────────────────────────────────────────────────────────
        total_metrics = db.query(FinancialMetric).count()
        total_reports = db.query(Report).filter(
            Report.extraction_status == "completed"
        ).count()
        avg_quality   = db.query(func.avg(Report.extraction_quality)).filter(
            Report.extraction_status == "completed"
        ).scalar() or 0

        print("\n=== Extraction Quality Summary ===")
        print(f"Completed reports    : {total_reports}")
        print(f"Total metrics stored : {total_metrics}")
        print(f"Avg quality score    : {avg_quality:.3f}")
        print(f"Validation issues    : {issues_found}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate extracted financial data")
    parser.add_argument("--company", metavar="SLUG")
    parser.add_argument("--year",    type=int, metavar="YYYY")
    args = parser.parse_args()
    validate_all(company_filter=args.company, year_filter=args.year)


if __name__ == "__main__":
    main()
