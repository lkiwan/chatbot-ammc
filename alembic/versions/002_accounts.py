"""Account tables: users + per-account chat history.

Revision ID: 002
Revises: 001
Create Date: 2026-09-28
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── users ─────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(256), nullable=False),
        sa.Column("token", sa.String(64), nullable=True),
        sa.Column("daily_msgs_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quota_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_token", "users", ["token"])

    # ── chat_history ───────────────────────────────────────────────────────
    op.create_table(
        "chat_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("company_name", sa.String(500), nullable=True),
        sa.Column("year", sa.String(20), nullable=True),
        sa.Column("sources", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_chat_history_user", "chat_history", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_chat_history_user", table_name="chat_history")
    op.drop_table("chat_history")
    op.drop_index("ix_users_token", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")