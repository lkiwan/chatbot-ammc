"""SQLAlchemy 2.0 models for the Financial Intelligence Platform."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger, Boolean, DateTime, Enum, Float, ForeignKey,
    Index, Integer, Numeric, String, Text, UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ── Enumerations ─────────────────────────────────────────────────────────────

class ExtractionStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    OCR_REQUIRED = "ocr_required"
    SKIPPED = "skipped"


class StatementType(str, enum.Enum):
    INCOME = "income_statement"
    BALANCE = "balance_sheet"
    CASHFLOW = "cash_flow"
    NOTES = "notes"
    OTHER = "other"


class MetricCategory(str, enum.Enum):
    REVENUE = "revenue"
    PROFITABILITY = "profitability"
    ASSETS = "assets"
    LIABILITIES = "liabilities"
    EQUITY = "equity"
    CASH_FLOW = "cash_flow"
    RATIO = "ratio"
    BANKING = "banking"
    OTHER = "other"


class ExtractionMethod(str, enum.Enum):
    TABLE = "table"
    TEXT_PATTERN = "text_pattern"
    COMPUTED = "computed"
    MANUAL = "manual"


# ── Companies ────────────────────────────────────────────────────────────────

class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    ticker: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    sector: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    subsector: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    country: Mapped[str] = mapped_column(String(10), default="MA", nullable=False)
    ammc_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, unique=True)
    ammc_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False
    )

    reports: Mapped[list["Report"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    metrics: Mapped[list["FinancialMetric"]] = relationship(back_populates="company")
    ratios: Mapped[list["FinancialRatio"]] = relationship(back_populates="company")
    shareholders: Mapped[list["Shareholder"]] = relationship(back_populates="company")

    __table_args__ = (
        Index("ix_companies_normalized_name", "normalized_name"),
        Index("ix_companies_sector", "sector"),
    )

    def __repr__(self) -> str:
        return f"<Company id={self.id} name={self.name!r}>"


# ── Reports ──────────────────────────────────────────────────────────────────

class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    report_type: Mapped[str] = mapped_column(String(100), default="annual_report", nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="fr", nullable=False)

    # File information
    pdf_filename: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    pdf_path: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    file_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    file_size: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    page_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    publication_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Extraction state
    extraction_status: Mapped[ExtractionStatus] = mapped_column(
        Enum(ExtractionStatus), default=ExtractionStatus.PENDING, nullable=False
    )
    extraction_quality: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    processing_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    processing_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ChromaDB link
    chroma_stem: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False
    )

    company: Mapped["Company"] = relationship(back_populates="reports")
    sections: Mapped[list["ReportSection"]] = relationship(back_populates="report", cascade="all, delete-orphan")
    metrics: Mapped[list["FinancialMetric"]] = relationship(back_populates="report", cascade="all, delete-orphan")
    income_statement: Mapped[Optional["IncomeStatement"]] = relationship(back_populates="report", uselist=False, cascade="all, delete-orphan")
    balance_sheet: Mapped[Optional["BalanceSheet"]] = relationship(back_populates="report", uselist=False, cascade="all, delete-orphan")
    cash_flow: Mapped[Optional["CashFlow"]] = relationship(back_populates="report", uselist=False, cascade="all, delete-orphan")
    ratios: Mapped[list["FinancialRatio"]] = relationship(back_populates="report", cascade="all, delete-orphan")
    shareholders: Mapped[list["Shareholder"]] = relationship(back_populates="report", cascade="all, delete-orphan")
    extraction_jobs: Mapped[list["ExtractionJob"]] = relationship(back_populates="report", cascade="all, delete-orphan")
    extraction_errors: Mapped[list["ExtractionError"]] = relationship(back_populates="report", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("company_id", "year", "report_type", name="uq_report_company_year_type"),
        Index("ix_reports_company_year", "company_id", "year"),
        Index("ix_reports_status", "extraction_status"),
        Index("ix_reports_file_hash", "file_hash"),
    )

    def __repr__(self) -> str:
        return f"<Report id={self.id} company_id={self.company_id} year={self.year}>"


# ── Report Sections ───────────────────────────────────────────────────────────

class ReportSection(Base):
    __tablename__ = "report_sections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), nullable=False)
    section_name: Mapped[str] = mapped_column(String(300), nullable=False)
    normalized_section_name: Mapped[str] = mapped_column(String(300), nullable=False)
    page_start: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    page_end: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    quality_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    report: Mapped["Report"] = relationship(back_populates="sections")

    __table_args__ = (
        Index("ix_sections_report", "report_id"),
        Index("ix_sections_name", "report_id", "normalized_section_name"),
    )


# ── Financial Metrics ─────────────────────────────────────────────────────────

class FinancialMetric(Base):
    """Individual extracted financial metric with full provenance."""
    __tablename__ = "financial_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)

    # Metric identification
    metric_name: Mapped[str] = mapped_column(String(300), nullable=False)
    normalized_metric_name: Mapped[str] = mapped_column(String(300), nullable=False)
    metric_category: Mapped[MetricCategory] = mapped_column(Enum(MetricCategory), default=MetricCategory.OTHER, nullable=False)
    statement_type: Mapped[Optional[StatementType]] = mapped_column(Enum(StatementType), nullable=True)

    # Value (both raw and normalized)
    raw_value: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    value: Mapped[Optional[float]] = mapped_column(Numeric(precision=20, scale=4), nullable=True)
    unit: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="MAD", nullable=False)
    period: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Provenance
    source_page: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source_section: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    source_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Quality
    confidence: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    extraction_method: Mapped[ExtractionMethod] = mapped_column(
        Enum(ExtractionMethod), default=ExtractionMethod.TABLE, nullable=False
    )
    is_validated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    validation_warning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False
    )

    company: Mapped["Company"] = relationship(back_populates="metrics")
    report: Mapped["Report"] = relationship(back_populates="metrics")

    __table_args__ = (
        UniqueConstraint("report_id", "normalized_metric_name", "year", "statement_type",
                         name="uq_metric_report_name_year"),
        Index("ix_metrics_company_year", "company_id", "year"),
        Index("ix_metrics_name_year", "company_id", "normalized_metric_name", "year"),
        Index("ix_metrics_category", "metric_category"),
    )


# ── Income Statement ──────────────────────────────────────────────────────────

class IncomeStatement(Base):
    __tablename__ = "income_statements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), nullable=False, unique=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="MAD", nullable=False)
    unit: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    revenue: Mapped[Optional[float]] = mapped_column(Numeric(20, 4), nullable=True)
    cost_of_revenue: Mapped[Optional[float]] = mapped_column(Numeric(20, 4), nullable=True)
    gross_profit: Mapped[Optional[float]] = mapped_column(Numeric(20, 4), nullable=True)
    operating_income: Mapped[Optional[float]] = mapped_column(Numeric(20, 4), nullable=True)
    ebitda: Mapped[Optional[float]] = mapped_column(Numeric(20, 4), nullable=True)
    finance_result: Mapped[Optional[float]] = mapped_column(Numeric(20, 4), nullable=True)
    profit_before_tax: Mapped[Optional[float]] = mapped_column(Numeric(20, 4), nullable=True)
    income_tax: Mapped[Optional[float]] = mapped_column(Numeric(20, 4), nullable=True)
    net_income: Mapped[Optional[float]] = mapped_column(Numeric(20, 4), nullable=True)
    net_income_group_share: Mapped[Optional[float]] = mapped_column(Numeric(20, 4), nullable=True)
    minority_interests: Mapped[Optional[float]] = mapped_column(Numeric(20, 4), nullable=True)
    net_banking_income: Mapped[Optional[float]] = mapped_column(Numeric(20, 4), nullable=True)

    source_page: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    report: Mapped["Report"] = relationship(back_populates="income_statement")

    __table_args__ = (
        Index("ix_income_company_year", "company_id", "year"),
    )


# ── Balance Sheet ─────────────────────────────────────────────────────────────

class BalanceSheet(Base):
    __tablename__ = "balance_sheets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), nullable=False, unique=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="MAD", nullable=False)
    unit: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Assets
    total_assets: Mapped[Optional[float]] = mapped_column(Numeric(20, 4), nullable=True)
    current_assets: Mapped[Optional[float]] = mapped_column(Numeric(20, 4), nullable=True)
    non_current_assets: Mapped[Optional[float]] = mapped_column(Numeric(20, 4), nullable=True)
    cash: Mapped[Optional[float]] = mapped_column(Numeric(20, 4), nullable=True)
    receivables: Mapped[Optional[float]] = mapped_column(Numeric(20, 4), nullable=True)
    inventory: Mapped[Optional[float]] = mapped_column(Numeric(20, 4), nullable=True)

    # Liabilities
    total_liabilities: Mapped[Optional[float]] = mapped_column(Numeric(20, 4), nullable=True)
    current_liabilities: Mapped[Optional[float]] = mapped_column(Numeric(20, 4), nullable=True)
    non_current_liabilities: Mapped[Optional[float]] = mapped_column(Numeric(20, 4), nullable=True)
    debt: Mapped[Optional[float]] = mapped_column(Numeric(20, 4), nullable=True)

    # Equity
    equity: Mapped[Optional[float]] = mapped_column(Numeric(20, 4), nullable=True)
    minority_interests_bs: Mapped[Optional[float]] = mapped_column(Numeric(20, 4), nullable=True)

    # Validation
    balance_check_passed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    balance_discrepancy_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    source_page: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    report: Mapped["Report"] = relationship(back_populates="balance_sheet")

    __table_args__ = (
        Index("ix_balance_company_year", "company_id", "year"),
    )


# ── Cash Flow ─────────────────────────────────────────────────────────────────

class CashFlow(Base):
    __tablename__ = "cash_flows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), nullable=False, unique=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="MAD", nullable=False)
    unit: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    operating_cash_flow: Mapped[Optional[float]] = mapped_column(Numeric(20, 4), nullable=True)
    investing_cash_flow: Mapped[Optional[float]] = mapped_column(Numeric(20, 4), nullable=True)
    financing_cash_flow: Mapped[Optional[float]] = mapped_column(Numeric(20, 4), nullable=True)
    capex: Mapped[Optional[float]] = mapped_column(Numeric(20, 4), nullable=True)
    free_cash_flow: Mapped[Optional[float]] = mapped_column(Numeric(20, 4), nullable=True)
    net_change_in_cash: Mapped[Optional[float]] = mapped_column(Numeric(20, 4), nullable=True)

    source_page: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    report: Mapped["Report"] = relationship(back_populates="cash_flow")

    __table_args__ = (
        Index("ix_cashflow_company_year", "company_id", "year"),
    )


# ── Financial Ratios ──────────────────────────────────────────────────────────

class FinancialRatio(Base):
    __tablename__ = "financial_ratios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)

    ratio_name: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[Optional[float]] = mapped_column(Numeric(20, 6), nullable=True)
    unit: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    formula: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    source_type: Mapped[str] = mapped_column(String(20), default="calculated", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.9, nullable=False)
    source_page: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    company: Mapped["Company"] = relationship(back_populates="ratios")
    report: Mapped["Report"] = relationship(back_populates="ratios")

    __table_args__ = (
        UniqueConstraint("report_id", "ratio_name", name="uq_ratio_report_name"),
        Index("ix_ratios_company_year", "company_id", "year"),
        Index("ix_ratios_name", "company_id", "ratio_name", "year"),
    )


# ── Shareholders ──────────────────────────────────────────────────────────────

class Shareholder(Base):
    __tablename__ = "shareholders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)

    shareholder_name: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_shareholder_name: Mapped[str] = mapped_column(String(500), nullable=False)
    ownership_percentage: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    shares: Mapped[Optional[float]] = mapped_column(Numeric(20, 0), nullable=True)
    share_class: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    source_page: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.7, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    company: Mapped["Company"] = relationship(back_populates="shareholders")
    report: Mapped["Report"] = relationship(back_populates="shareholders")

    __table_args__ = (
        Index("ix_shareholders_company_year", "company_id", "year"),
    )


# ── Extraction Jobs ───────────────────────────────────────────────────────────

class ExtractionJob(Base):
    __tablename__ = "extraction_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    metrics_extracted: Mapped[int] = mapped_column(Integer, default=0)
    sections_extracted: Mapped[int] = mapped_column(Integer, default=0)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    report: Mapped["Report"] = relationship(back_populates="extraction_jobs")

    __table_args__ = (
        Index("ix_jobs_report", "report_id"),
    )


# ── Extraction Errors ─────────────────────────────────────────────────────────

class ExtractionError(Base):
    __tablename__ = "extraction_errors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[Optional[int]] = mapped_column(ForeignKey("reports.id", ondelete="SET NULL"), nullable=True)
    filename: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    error_type: Mapped[str] = mapped_column(String(200), nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    stack_trace: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    report: Mapped[Optional["Report"]] = relationship(back_populates="extraction_errors")

    __table_args__ = (
        Index("ix_errors_report", "report_id"),
        Index("ix_errors_resolved", "resolved"),
    )
