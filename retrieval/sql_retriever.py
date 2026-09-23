"""
SQL retriever: read-only parameterized queries against PostgreSQL.

All queries are parameterized — no string interpolation of user input.
Returns JSON-serializable dicts; never exposes ORM objects.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy import text

from db.session import get_db

logger = logging.getLogger(__name__)


@dataclass
class SQLResult:
    rows: list[dict[str, Any]]
    query_description: str
    row_count: int = field(init=False)
    error: Optional[str] = None

    def __post_init__(self) -> None:
        self.row_count = len(self.rows)

    @property
    def is_empty(self) -> bool:
        return self.row_count == 0

    def as_text(self) -> str:
        """Render rows as a plain-text table for LLM context injection."""
        if self.is_empty:
            return f"[No data found for: {self.query_description}]"
        headers = list(self.rows[0].keys())
        lines = [" | ".join(headers)]
        lines.append("-" * len(lines[0]))
        for row in self.rows:
            lines.append(" | ".join(str(row.get(h, "")) for h in headers))
        return "\n".join(lines)


class SQLRetriever:
    """Execute read-only SQL queries for financial data retrieval."""

    # ── Public query methods ──────────────────────────────────────────────────

    def get_metric(
        self,
        company_normalized: str,
        metric_name: str,
        year: Optional[int] = None,
    ) -> SQLResult:
        """Retrieve a specific financial metric for a company."""
        query = text("""
            SELECT
                c.name         AS company,
                fm.year,
                fm.normalized_metric_name AS metric,
                fm.value,
                fm.unit,
                fm.currency,
                fm.confidence,
                fm.validation_warning
            FROM financial_metrics fm
            JOIN companies c ON c.id = fm.company_id
            WHERE c.normalized_name = :company
              AND fm.normalized_metric_name = :metric
              AND (:year IS NULL OR fm.year = :year)
            ORDER BY fm.year DESC
            LIMIT 10
        """)
        return self._run(
            query,
            {"company": company_normalized, "metric": metric_name, "year": year},
            description=f"{metric_name} for {company_normalized}" + (f" ({year})" if year else ""),
        )

    def compare_metric_across_years(
        self,
        company_normalized: str,
        metric_name: str,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
    ) -> SQLResult:
        """Retrieve metric evolution across years for a company."""
        query = text("""
            SELECT
                c.name         AS company,
                fm.year,
                fm.normalized_metric_name AS metric,
                fm.value,
                fm.unit,
                fm.currency,
                fm.confidence
            FROM financial_metrics fm
            JOIN companies c ON c.id = fm.company_id
            WHERE c.normalized_name = :company
              AND fm.normalized_metric_name = :metric
              AND (:year_from IS NULL OR fm.year >= :year_from)
              AND (:year_to   IS NULL OR fm.year <= :year_to)
            ORDER BY fm.year ASC
        """)
        return self._run(
            query,
            {"company": company_normalized, "metric": metric_name,
             "year_from": year_from, "year_to": year_to},
            description=f"{metric_name} evolution for {company_normalized}",
        )

    def compare_metric_across_companies(
        self,
        metric_name: str,
        year: int,
        sector: Optional[str] = None,
    ) -> SQLResult:
        """Compare a metric across all companies for a given year."""
        query = text("""
            SELECT
                c.name         AS company,
                c.sector,
                fm.year,
                fm.normalized_metric_name AS metric,
                fm.value,
                fm.unit,
                fm.currency
            FROM financial_metrics fm
            JOIN companies c ON c.id = fm.company_id
            WHERE fm.normalized_metric_name = :metric
              AND fm.year = :year
              AND (:sector IS NULL OR c.sector = :sector)
              AND fm.confidence >= 0.4
            ORDER BY fm.value DESC NULLS LAST
        """)
        return self._run(
            query,
            {"metric": metric_name, "year": year, "sector": sector},
            description=f"{metric_name} comparison across companies ({year})",
        )

    def get_income_statement(
        self,
        company_normalized: str,
        year: int,
    ) -> SQLResult:
        """Retrieve the full income statement for a company/year."""
        query = text("""
            SELECT
                c.name         AS company,
                ist.year,
                ist.revenue,
                ist.net_banking_income,
                ist.gross_profit,
                ist.operating_income,
                ist.ebitda,
                ist.finance_result,
                ist.profit_before_tax,
                ist.income_tax,
                ist.net_income,
                ist.net_income_group_share,
                ist.currency,
                ist.unit,
                ist.confidence
            FROM income_statements ist
            JOIN companies c ON c.id = ist.company_id
            WHERE c.normalized_name = :company
              AND ist.year = :year
            LIMIT 1
        """)
        return self._run(
            query,
            {"company": company_normalized, "year": year},
            description=f"Income statement for {company_normalized} ({year})",
        )

    def get_balance_sheet(
        self,
        company_normalized: str,
        year: int,
    ) -> SQLResult:
        """Retrieve the full balance sheet for a company/year."""
        query = text("""
            SELECT
                c.name         AS company,
                bs.year,
                bs.total_assets,
                bs.current_assets,
                bs.non_current_assets,
                bs.cash,
                bs.receivables,
                bs.inventory,
                bs.total_liabilities,
                bs.current_liabilities,
                bs.non_current_liabilities,
                bs.debt,
                bs.equity,
                bs.balance_check_passed,
                bs.balance_discrepancy_pct,
                bs.currency,
                bs.unit
            FROM balance_sheets bs
            JOIN companies c ON c.id = bs.company_id
            WHERE c.normalized_name = :company
              AND bs.year = :year
            LIMIT 1
        """)
        return self._run(
            query,
            {"company": company_normalized, "year": year},
            description=f"Balance sheet for {company_normalized} ({year})",
        )

    def get_cash_flow(
        self,
        company_normalized: str,
        year: int,
    ) -> SQLResult:
        """Retrieve the cash flow statement for a company/year."""
        query = text("""
            SELECT
                c.name         AS company,
                cf.year,
                cf.operating_cash_flow,
                cf.investing_cash_flow,
                cf.financing_cash_flow,
                cf.capex,
                cf.free_cash_flow,
                cf.net_change_in_cash,
                cf.currency,
                cf.unit
            FROM cash_flows cf
            JOIN companies c ON c.id = cf.company_id
            WHERE c.normalized_name = :company
              AND cf.year = :year
            LIMIT 1
        """)
        return self._run(
            query,
            {"company": company_normalized, "year": year},
            description=f"Cash flow for {company_normalized} ({year})",
        )

    def get_financial_ratios(
        self,
        company_normalized: str,
        year: int,
    ) -> SQLResult:
        """Retrieve financial ratios for a company/year."""
        query = text("""
            SELECT
                c.name         AS company,
                fr.year,
                fr.ratio_name,
                fr.value,
                fr.formula,
                fr.source_type
            FROM financial_ratios fr
            JOIN companies c ON c.id = fr.company_id
            WHERE c.normalized_name = :company
              AND fr.year = :year
            ORDER BY fr.ratio_name
        """)
        return self._run(
            query,
            {"company": company_normalized, "year": year},
            description=f"Ratios for {company_normalized} ({year})",
        )

    def get_shareholders(
        self,
        company_normalized: str,
        year: Optional[int] = None,
    ) -> SQLResult:
        """Retrieve shareholder structure for a company."""
        query = text("""
            SELECT
                c.name         AS company,
                sh.year,
                sh.shareholder_name,
                sh.ownership_percentage,
                sh.shares
            FROM shareholders sh
            JOIN companies c ON c.id = sh.company_id
            WHERE c.normalized_name = :company
              AND (:year IS NULL OR sh.year = :year)
            ORDER BY sh.year DESC, sh.ownership_percentage DESC NULLS LAST
            LIMIT 50
        """)
        return self._run(
            query,
            {"company": company_normalized, "year": year},
            description=f"Shareholders for {company_normalized}",
        )

    def list_companies(self, sector: Optional[str] = None) -> SQLResult:
        """List all companies, optionally filtered by sector."""
        query = text("""
            SELECT
                c.normalized_name,
                c.name,
                c.ticker,
                c.sector,
                COUNT(DISTINCT r.year) AS n_reports,
                MIN(r.year)            AS year_first,
                MAX(r.year)            AS year_last
            FROM companies c
            LEFT JOIN reports r ON r.company_id = c.id
            WHERE (:sector IS NULL OR c.sector = :sector)
            GROUP BY c.id, c.normalized_name, c.name, c.ticker, c.sector
            ORDER BY c.name
        """)
        return self._run(
            query,
            {"sector": sector},
            description="Company list" + (f" (sector={sector})" if sector else ""),
        )

    def get_company_available_years(self, company_normalized: str) -> SQLResult:
        """List years for which data is available for a company."""
        query = text("""
            SELECT
                c.name,
                r.year,
                r.extraction_status,
                r.extraction_quality
            FROM reports r
            JOIN companies c ON c.id = r.company_id
            WHERE c.normalized_name = :company
            ORDER BY r.year DESC
        """)
        return self._run(
            query,
            {"company": company_normalized},
            description=f"Available years for {company_normalized}",
        )

    # ── Internal ──────────────────────────────────────────────────────────────

    def _run(
        self,
        query,
        params: dict[str, Any],
        description: str,
    ) -> SQLResult:
        """Execute a query and return an SQLResult."""
        try:
            with get_db() as db:
                result = db.execute(query, params)
                columns = list(result.keys())
                rows = [dict(zip(columns, row)) for row in result.fetchall()]
                return SQLResult(rows=rows, query_description=description)
        except Exception as exc:
            logger.error("SQL query failed [%s]: %s", description, exc)
            return SQLResult(
                rows=[],
                query_description=description,
                error=f"{type(exc).__name__}: {exc}",
            )
