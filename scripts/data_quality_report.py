"""
Generate a data quality report across all companies and years.

Outputs a plain-text table to stdout.
Run: python scripts/data_quality_report.py [--sector SECTOR]
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, text

from db.models import Company, FinancialMetric, Report
from db.session import check_connection, get_db

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_COL_W = [30, 6, 8, 10, 8, 10]
_HEADERS = ["Company", "Year", "Status", "# Metrics", "Quality", "Warnings"]


def _fmt_row(cols: list) -> str:
    return "  ".join(str(c).ljust(_COL_W[i]) for i, c in enumerate(cols))


def report(sector_filter: Optional[str] = None) -> None:
    if not check_connection():
        logger.error("Cannot connect to PostgreSQL")
        sys.exit(1)

    with get_db() as db:
        q = (
            db.query(
                Company.name,
                Report.year,
                Report.extraction_status,
                Report.extraction_quality,
                func.count(FinancialMetric.id).label("n_metrics"),
            )
            .outerjoin(Report,       Report.company_id     == Company.id)
            .outerjoin(FinancialMetric, FinancialMetric.report_id == Report.id)
        )
        if sector_filter:
            q = q.filter(Company.sector == sector_filter)
        q = q.group_by(
            Company.name, Report.year, Report.extraction_status, Report.extraction_quality
        ).order_by(Company.name, Report.year.desc())

        rows = q.all()

    if not rows:
        print("No data found.")
        return

    header_line = _fmt_row(_HEADERS)
    print(header_line)
    print("-" * len(header_line))

    prev_company = None
    for row in rows:
        company_name, year, status, quality, n_metrics = row
        if company_name != prev_company:
            prev_company = company_name
        else:
            company_name = ""  # don't repeat company name

        quality_str = f"{quality:.2f}" if quality is not None else "—"
        print(_fmt_row([
            company_name or "",
            year or "—",
            status or "—",
            n_metrics,
            quality_str,
            "",
        ]))

    # Totals
    with get_db() as db:
        total_cos = db.query(Company).count()
        total_rpt = db.query(Report).count()
        done_rpt  = db.query(Report).filter(Report.extraction_status == "completed").count()
        total_m   = db.query(FinancialMetric).count()
        avg_q     = db.query(func.avg(Report.extraction_quality)).filter(
            Report.extraction_status == "completed"
        ).scalar() or 0

    print()
    print(f"Companies    : {total_cos}")
    print(f"Reports      : {total_rpt} total, {done_rpt} extracted")
    print(f"Metrics      : {total_m}")
    print(f"Avg quality  : {avg_q:.3f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Data quality report")
    parser.add_argument("--sector", metavar="SECTOR", help="Filter by sector")
    args = parser.parse_args()
    report(sector_filter=args.sector)


if __name__ == "__main__":
    main()
