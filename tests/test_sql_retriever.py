"""
Integration tests for retrieval.sql_retriever.

These tests require a running PostgreSQL instance with populated data.
They are skipped automatically if the DB is not reachable.
"""
from __future__ import annotations

import pytest

from db.session import check_connection, check_schema


# Skip all tests if DB not available or schema not migrated
pytestmark = pytest.mark.skipif(
    not check_connection() or not check_schema(),
    reason="PostgreSQL not reachable or schema missing — run: docker compose up -d && alembic upgrade head",
)


@pytest.fixture(scope="module")
def retriever():
    from retrieval.sql_retriever import SQLRetriever
    return SQLRetriever()


class TestSQLRetriever:
    def test_list_companies_returns_result(self, retriever):
        result = retriever.list_companies()
        # Even if DB is empty, no error should occur
        assert result.error is None

    def test_list_companies_with_sector(self, retriever):
        result = retriever.list_companies(sector="Banques")
        assert result.error is None

    def test_get_metric_unknown_company(self, retriever):
        result = retriever.get_metric("nonexistent_company_xyz", "net_income", 2022)
        assert result.error is None
        assert result.is_empty is True

    def test_compare_across_years_unknown(self, retriever):
        result = retriever.compare_metric_across_years(
            "nonexistent_xyz", "revenue", 2018, 2023
        )
        assert result.error is None
        assert result.is_empty is True

    def test_compare_across_companies_returns_result(self, retriever):
        result = retriever.compare_metric_across_companies("net_income", 2022)
        assert result.error is None

    def test_as_text_empty(self, retriever):
        result = retriever.get_metric("nonexistent_xyz", "net_income", 2022)
        text = result.as_text()
        assert "No data" in text

    def test_get_shareholders_unknown(self, retriever):
        result = retriever.get_shareholders("nonexistent_xyz")
        assert result.error is None
        assert result.is_empty is True

    def test_get_income_statement_unknown(self, retriever):
        result = retriever.get_income_statement("nonexistent_xyz", 2022)
        assert result.error is None

    def test_get_balance_sheet_unknown(self, retriever):
        result = retriever.get_balance_sheet("nonexistent_xyz", 2022)
        assert result.error is None

    def test_get_cash_flow_unknown(self, retriever):
        result = retriever.get_cash_flow("nonexistent_xyz", 2022)
        assert result.error is None

    def test_get_company_years_unknown(self, retriever):
        result = retriever.get_company_available_years("nonexistent_xyz")
        assert result.error is None
