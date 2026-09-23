"""
Financial data validation rules.

Flags data quality issues without deleting data.
Returns warnings rather than hard failures.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ValidationResult:
    passed: bool
    warnings: list[str]
    discrepancy_pct: Optional[float] = None


def validate_balance_sheet(
    total_assets: Optional[float],
    total_liabilities: Optional[float],
    equity: Optional[float],
    tolerance_pct: float = 5.0,
) -> ValidationResult:
    """Check Assets ≈ Liabilities + Equity.

    Args:
        tolerance_pct: Acceptable discrepancy percentage (default 5%).
    """
    warnings: list[str] = []

    if total_assets is None:
        return ValidationResult(passed=False, warnings=["total_assets is missing"])

    computed_liab_equity: Optional[float] = None
    if total_liabilities is not None and equity is not None:
        computed_liab_equity = total_liabilities + equity
    elif total_liabilities is not None:
        warnings.append("equity missing — balance equation cannot be fully verified")
    elif equity is not None:
        warnings.append("total_liabilities missing — balance equation cannot be fully verified")
    else:
        return ValidationResult(passed=False, warnings=["both total_liabilities and equity are missing"])

    if computed_liab_equity is None:
        return ValidationResult(passed=False, warnings=warnings)

    if total_assets == 0:
        return ValidationResult(passed=False, warnings=["total_assets = 0 — suspicious"])

    discrepancy = abs(total_assets - computed_liab_equity) / abs(total_assets) * 100
    if discrepancy > tolerance_pct:
        warnings.append(
            f"Balance equation violated: assets={total_assets:,.0f}, "
            f"liabilities+equity={computed_liab_equity:,.0f}, "
            f"discrepancy={discrepancy:.1f}%"
        )
        return ValidationResult(passed=False, warnings=warnings, discrepancy_pct=discrepancy)

    return ValidationResult(passed=True, warnings=warnings, discrepancy_pct=discrepancy)


def validate_income_statement(
    revenue: Optional[float],
    net_income: Optional[float],
    gross_profit: Optional[float] = None,
) -> ValidationResult:
    """Validate income statement logical consistency."""
    warnings: list[str] = []

    if revenue is not None and net_income is not None:
        # Net income can't be larger than revenue (for non-banks, non-financials)
        if abs(net_income) > abs(revenue) * 2:
            warnings.append(
                f"net_income ({net_income:,.0f}) is unusually large vs revenue ({revenue:,.0f})"
            )

    if gross_profit is not None and revenue is not None and revenue != 0:
        margin = gross_profit / revenue
        if margin > 1.05:
            warnings.append(f"gross_margin={margin:.1%} > 100% — check unit consistency")
        if margin < -0.5:
            warnings.append(f"gross_margin={margin:.1%} very negative — check sign")

    return ValidationResult(passed=len(warnings) == 0, warnings=warnings)


def validate_percentage(value: Optional[float], field_name: str) -> ValidationResult:
    """Check a percentage value is in [0, 100]."""
    if value is None:
        return ValidationResult(passed=True, warnings=[])
    if not (-150 <= value <= 150):
        return ValidationResult(
            passed=False,
            warnings=[f"{field_name}={value:.2f} out of expected percentage range [-150, 150]"]
        )
    return ValidationResult(passed=True, warnings=[])


def validate_year(year: Optional[int]) -> ValidationResult:
    if year is None:
        return ValidationResult(passed=False, warnings=["year is None"])
    if not (1980 <= year <= 2030):
        return ValidationResult(passed=False, warnings=[f"year={year} is implausible"])
    return ValidationResult(passed=True, warnings=[])
