"""Initial schema: companies, reports, metrics, statements, ratios, shareholders.

Revision ID: 001
Revises:
Create Date: 2026-09-23
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── companies ─────────────────────────────────────────────────────────
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("normalized_name", sa.String(500), nullable=False),
        sa.Column("ticker", sa.String(20), nullable=True),
        sa.Column("sector", sa.String(200), nullable=True),
        sa.Column("subsector", sa.String(200), nullable=True),
        sa.Column("country", sa.String(10), nullable=False, server_default="MA"),
        sa.Column("ammc_id", sa.String(50), nullable=True),
        sa.Column("ammc_url", sa.String(1000), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("normalized_name"),
        sa.UniqueConstraint("ammc_id"),
    )
    op.create_index("ix_companies_normalized_name", "companies", ["normalized_name"])
    op.create_index("ix_companies_sector", "companies", ["sector"])

    # ── reports ───────────────────────────────────────────────────────────
    op.create_table(
        "reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(1000), nullable=True),
        sa.Column("report_type", sa.String(100), nullable=False, server_default="annual_report"),
        sa.Column("language", sa.String(10), nullable=False, server_default="fr"),
        sa.Column("pdf_filename", sa.String(500), nullable=True),
        sa.Column("pdf_path", sa.String(2000), nullable=True),
        sa.Column("source_url", sa.String(2000), nullable=True),
        sa.Column("file_hash", sa.String(64), nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("publication_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("extraction_status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("extraction_quality", sa.Float(), nullable=True),
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("chroma_stem", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "year", "report_type", name="uq_report_company_year_type"),
    )
    op.create_index("ix_reports_company_year", "reports", ["company_id", "year"])
    op.create_index("ix_reports_status", "reports", ["extraction_status"])
    op.create_index("ix_reports_file_hash", "reports", ["file_hash"])

    # ── report_sections ───────────────────────────────────────────────────
    op.create_table(
        "report_sections",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("report_id", sa.Integer(), nullable=False),
        sa.Column("section_name", sa.String(300), nullable=False),
        sa.Column("normalized_section_name", sa.String(300), nullable=False),
        sa.Column("page_start", sa.Integer(), nullable=True),
        sa.Column("page_end", sa.Integer(), nullable=True),
        sa.Column("content", sa.Text, nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sections_report", "report_sections", ["report_id"])
    op.create_index("ix_sections_name", "report_sections", ["report_id", "normalized_section_name"])

    # ── financial_metrics ─────────────────────────────────────────────────
    op.create_table(
        "financial_metrics",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("report_id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("metric_name", sa.String(300), nullable=False),
        sa.Column("normalized_metric_name", sa.String(300), nullable=False),
        sa.Column("metric_category", sa.String(50), nullable=False, server_default="other"),
        sa.Column("statement_type", sa.String(50), nullable=True),
        sa.Column("raw_value", sa.String(200), nullable=True),
        sa.Column("value", sa.Numeric(20, 4), nullable=True),
        sa.Column("unit", sa.String(50), nullable=True),
        sa.Column("currency", sa.String(10), nullable=False, server_default="MAD"),
        sa.Column("period", sa.String(50), nullable=True),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("source_section", sa.String(300), nullable=True),
        sa.Column("source_text", sa.Text, nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("extraction_method", sa.String(50), nullable=False, server_default="table"),
        sa.Column("is_validated", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("validation_warning", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("report_id", "normalized_metric_name", "year", "statement_type",
                            name="uq_metric_report_name_year"),
    )
    op.create_index("ix_metrics_company_year", "financial_metrics", ["company_id", "year"])
    op.create_index("ix_metrics_name_year", "financial_metrics", ["company_id", "normalized_metric_name", "year"])
    op.create_index("ix_metrics_category", "financial_metrics", ["metric_category"])

    # ── income_statements ─────────────────────────────────────────────────
    op.create_table(
        "income_statements",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("report_id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, server_default="MAD"),
        sa.Column("unit", sa.String(20), nullable=True),
        sa.Column("revenue", sa.Numeric(20, 4), nullable=True),
        sa.Column("cost_of_revenue", sa.Numeric(20, 4), nullable=True),
        sa.Column("gross_profit", sa.Numeric(20, 4), nullable=True),
        sa.Column("operating_income", sa.Numeric(20, 4), nullable=True),
        sa.Column("ebitda", sa.Numeric(20, 4), nullable=True),
        sa.Column("finance_result", sa.Numeric(20, 4), nullable=True),
        sa.Column("profit_before_tax", sa.Numeric(20, 4), nullable=True),
        sa.Column("income_tax", sa.Numeric(20, 4), nullable=True),
        sa.Column("net_income", sa.Numeric(20, 4), nullable=True),
        sa.Column("net_income_group_share", sa.Numeric(20, 4), nullable=True),
        sa.Column("minority_interests", sa.Numeric(20, 4), nullable=True),
        sa.Column("net_banking_income", sa.Numeric(20, 4), nullable=True),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("report_id"),
    )
    op.create_index("ix_income_company_year", "income_statements", ["company_id", "year"])

    # ── balance_sheets ────────────────────────────────────────────────────
    op.create_table(
        "balance_sheets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("report_id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, server_default="MAD"),
        sa.Column("unit", sa.String(20), nullable=True),
        sa.Column("total_assets", sa.Numeric(20, 4), nullable=True),
        sa.Column("current_assets", sa.Numeric(20, 4), nullable=True),
        sa.Column("non_current_assets", sa.Numeric(20, 4), nullable=True),
        sa.Column("cash", sa.Numeric(20, 4), nullable=True),
        sa.Column("receivables", sa.Numeric(20, 4), nullable=True),
        sa.Column("inventory", sa.Numeric(20, 4), nullable=True),
        sa.Column("total_liabilities", sa.Numeric(20, 4), nullable=True),
        sa.Column("current_liabilities", sa.Numeric(20, 4), nullable=True),
        sa.Column("non_current_liabilities", sa.Numeric(20, 4), nullable=True),
        sa.Column("debt", sa.Numeric(20, 4), nullable=True),
        sa.Column("equity", sa.Numeric(20, 4), nullable=True),
        sa.Column("minority_interests_bs", sa.Numeric(20, 4), nullable=True),
        sa.Column("balance_check_passed", sa.Boolean(), nullable=True),
        sa.Column("balance_discrepancy_pct", sa.Float(), nullable=True),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("report_id"),
    )
    op.create_index("ix_balance_company_year", "balance_sheets", ["company_id", "year"])

    # ── cash_flows ────────────────────────────────────────────────────────
    op.create_table(
        "cash_flows",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("report_id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, server_default="MAD"),
        sa.Column("unit", sa.String(20), nullable=True),
        sa.Column("operating_cash_flow", sa.Numeric(20, 4), nullable=True),
        sa.Column("investing_cash_flow", sa.Numeric(20, 4), nullable=True),
        sa.Column("financing_cash_flow", sa.Numeric(20, 4), nullable=True),
        sa.Column("capex", sa.Numeric(20, 4), nullable=True),
        sa.Column("free_cash_flow", sa.Numeric(20, 4), nullable=True),
        sa.Column("net_change_in_cash", sa.Numeric(20, 4), nullable=True),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("report_id"),
    )
    op.create_index("ix_cashflow_company_year", "cash_flows", ["company_id", "year"])

    # ── financial_ratios ──────────────────────────────────────────────────
    op.create_table(
        "financial_ratios",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("report_id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("ratio_name", sa.String(100), nullable=False),
        sa.Column("value", sa.Numeric(20, 6), nullable=True),
        sa.Column("unit", sa.String(20), nullable=True),
        sa.Column("formula", sa.String(500), nullable=True),
        sa.Column("source_type", sa.String(20), nullable=False, server_default="calculated"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.9"),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("report_id", "ratio_name", name="uq_ratio_report_name"),
    )
    op.create_index("ix_ratios_company_year", "financial_ratios", ["company_id", "year"])
    op.create_index("ix_ratios_name", "financial_ratios", ["company_id", "ratio_name", "year"])

    # ── shareholders ──────────────────────────────────────────────────────
    op.create_table(
        "shareholders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("report_id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("shareholder_name", sa.String(500), nullable=False),
        sa.Column("normalized_shareholder_name", sa.String(500), nullable=False),
        sa.Column("ownership_percentage", sa.Float(), nullable=True),
        sa.Column("shares", sa.Numeric(20, 0), nullable=True),
        sa.Column("share_class", sa.String(50), nullable=True),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.7"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shareholders_company_year", "shareholders", ["company_id", "year"])

    # ── extraction_jobs ───────────────────────────────────────────────────
    op.create_table(
        "extraction_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("report_id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("metrics_extracted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sections_extracted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_jobs_report", "extraction_jobs", ["report_id"])

    # ── extraction_errors ─────────────────────────────────────────────────
    op.create_table(
        "extraction_errors",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("report_id", sa.Integer(), nullable=True),
        sa.Column("filename", sa.String(500), nullable=True),
        sa.Column("error_type", sa.String(200), nullable=False),
        sa.Column("error_message", sa.Text, nullable=False),
        sa.Column("stack_trace", sa.Text, nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("resolved", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_errors_report", "extraction_errors", ["report_id"])
    op.create_index("ix_errors_resolved", "extraction_errors", ["resolved"])


def downgrade() -> None:
    op.drop_table("extraction_errors")
    op.drop_table("extraction_jobs")
    op.drop_table("shareholders")
    op.drop_table("financial_ratios")
    op.drop_table("cash_flows")
    op.drop_table("balance_sheets")
    op.drop_table("income_statements")
    op.drop_table("financial_metrics")
    op.drop_table("report_sections")
    op.drop_table("reports")
    op.drop_table("companies")
