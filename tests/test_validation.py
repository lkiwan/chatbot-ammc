"""
Unit tests for extraction.validator — financial data validation rules.
"""
import pytest
from extraction.validator import (
    validate_balance_sheet,
    validate_income_statement,
    validate_percentage,
    validate_year,
)


class TestBalanceSheet:
    def test_perfect_balance(self):
        result = validate_balance_sheet(
            total_assets=1_000_000,
            total_liabilities=600_000,
            equity=400_000,
        )
        assert result.passed is True
        assert result.discrepancy_pct == pytest.approx(0.0, abs=0.01)

    def test_within_tolerance(self):
        # 3% discrepancy — within 5% default
        result = validate_balance_sheet(
            total_assets=1_000_000,
            total_liabilities=600_000,
            equity=370_000,  # sum = 970_000, diff = 30_000 = 3%
        )
        assert result.passed is True

    def test_exceeds_tolerance(self):
        result = validate_balance_sheet(
            total_assets=1_000_000,
            total_liabilities=500_000,
            equity=400_000,  # sum = 900_000, diff = 10%
        )
        assert result.passed is False
        assert result.discrepancy_pct > 5.0

    def test_missing_assets(self):
        result = validate_balance_sheet(None, 500_000, 400_000)
        assert result.passed is False

    def test_missing_equity(self):
        result = validate_balance_sheet(1_000_000, 600_000, None)
        assert result.passed is False
        assert any("equity" in w for w in result.warnings)

    def test_zero_assets(self):
        result = validate_balance_sheet(0, 0, 0)
        assert result.passed is False

    def test_custom_tolerance(self):
        result = validate_balance_sheet(
            total_assets=1_000_000,
            total_liabilities=500_000,
            equity=450_000,  # 5% discrepancy
            tolerance_pct=3.0,
        )
        assert result.passed is False


class TestIncomeStatement:
    def test_valid(self):
        result = validate_income_statement(
            revenue=1_000_000,
            net_income=100_000,
            gross_profit=400_000,
        )
        assert result.passed is True

    def test_net_income_larger_than_revenue(self):
        result = validate_income_statement(
            revenue=100_000,
            net_income=300_000,   # 3× revenue — suspicious
        )
        assert result.passed is False

    def test_gross_margin_over_100_pct(self):
        result = validate_income_statement(
            revenue=100_000,
            net_income=10_000,
            gross_profit=110_000,  # 110% margin
        )
        assert result.passed is False

    def test_none_values(self):
        # Should not crash
        result = validate_income_statement(None, None)
        assert result.passed is True

    def test_negative_net_income_ok(self):
        result = validate_income_statement(
            revenue=500_000,
            net_income=-50_000,   # loss — valid
        )
        assert result.passed is True


class TestValidatePercentage:
    def test_valid(self):
        assert validate_percentage(45.0, "roe").passed is True

    def test_over_range(self):
        assert validate_percentage(200.0, "roe").passed is False

    def test_none(self):
        assert validate_percentage(None, "roe").passed is True


class TestValidateYear:
    def test_valid(self):
        assert validate_year(2022).passed is True

    def test_too_old(self):
        assert validate_year(1950).passed is False

    def test_too_future(self):
        assert validate_year(2099).passed is False

    def test_none(self):
        assert validate_year(None).passed is False
