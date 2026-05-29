"""add phase 3 qa security tables

Revision ID: 0008_phase3_qa_security
Revises: 0007_merge_phase2_heads
Create Date: 2026-05-29
"""

from alembic import op
import sqlalchemy as sa


revision = "0008_phase3_qa_security"
down_revision = "0007_merge_phase2_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "qa_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_qa_sessions_user_id", "qa_sessions", ["user_id"])
    op.create_index("ix_qa_sessions_user_updated", "qa_sessions", ["user_id", "updated_at"])

    op.create_table(
        "qa_messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("qa_sessions.id"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("reply_to_id", sa.String(36), sa.ForeignKey("qa_messages.id"), nullable=True),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="completed"),
        sa.Column(
            "model_call_log_id",
            sa.String(36),
            sa.ForeignKey("model_call_logs.id"),
            nullable=True,
        ),
        sa.Column("error_summary", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_qa_messages_session_id", "qa_messages", ["session_id"])
    op.create_index(
        "ix_qa_messages_session_created", "qa_messages", ["session_id", "created_at"]
    )

    op.create_table(
        "qa_citations",
        sa.Column(
            "answer_message_id",
            sa.String(36),
            sa.ForeignKey("qa_messages.id"),
            primary_key=True,
        ),
        sa.Column(
            "knowledge_item_id",
            sa.String(36),
            sa.ForeignKey("knowledge_items.id"),
            primary_key=True,
        ),
        sa.Column("rank", sa.Integer, nullable=False),
        sa.Column("excerpt", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("qa_citations")
    op.drop_index("ix_qa_messages_session_created", table_name="qa_messages")
    op.drop_index("ix_qa_messages_session_id", table_name="qa_messages")
    op.drop_table("qa_messages")
    op.drop_index("ix_qa_sessions_user_updated", table_name="qa_sessions")
    op.drop_index("ix_qa_sessions_user_id", table_name="qa_sessions")
    op.drop_table("qa_sessions")
