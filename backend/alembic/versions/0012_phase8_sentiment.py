"""add phase 8 tables (sentiment_tasks, sentiment_reports)

Revision ID: 0012_phase8_sentiment
Revises: 0011_phase7_employees_tools_servers
Create Date: 2026-05-31
"""

from alembic import op
import sqlalchemy as sa


revision = "0012_phase8_sentiment"
down_revision = "0011_phase7_employees_tools_servers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- sentiment_tasks ---
    op.create_table(
        "sentiment_tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("task_type", sa.String(40), nullable=False, server_default="full"),
        sa.Column("data_scope", sa.JSON, nullable=True),
        sa.Column("include_chat_data", sa.Boolean, nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("progress", sa.Integer, nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_sentiment_tasks_status", "sentiment_tasks",
        ["status", "created_at"],
    )
    op.create_index(
        "ix_sentiment_tasks_creator", "sentiment_tasks",
        ["created_by", "created_at"],
    )

    # --- sentiment_reports ---
    op.create_table(
        "sentiment_reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "task_id", sa.String(36),
            sa.ForeignKey("sentiment_tasks.id"), nullable=False,
        ),
        sa.Column("report_type", sa.String(40), nullable=False),
        sa.Column("report_data", sa.JSON, nullable=False),
        sa.Column("summary_text", sa.Text, nullable=True),
        sa.Column("source_item_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_sentiment_reports_task", "sentiment_reports",
        ["task_id", "report_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_sentiment_reports_task", table_name="sentiment_reports")
    op.drop_table("sentiment_reports")
    op.drop_index("ix_sentiment_tasks_creator", table_name="sentiment_tasks")
    op.drop_index("ix_sentiment_tasks_status", table_name="sentiment_tasks")
    op.drop_table("sentiment_tasks")
