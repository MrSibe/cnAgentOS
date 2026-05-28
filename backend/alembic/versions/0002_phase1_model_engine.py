"""create model engine tables

Revision ID: 0002_phase1_model_engine
Revises: 0001_phase1_platform
Create Date: 2026-05-27
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_phase1_model_engine"
down_revision = "0001_phase1_platform"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_configs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("provider_type", sa.String(length=40), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("base_url", sa.String(length=512), nullable=False),
        sa.Column("credential_ciphertext", sa.Text(), nullable=False),
        sa.Column("credential_mask", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    # 单一默认模型约束：使用部分唯一索引确保只有一个 is_default=true
    op.create_index(
        "ix_model_configs_is_default",
        "model_configs",
        ["is_default"],
        postgresql_where=sa.text("is_default = true"),
        unique=True,
    )

    op.create_table(
        "model_call_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("model_config_id", sa.String(length=36), nullable=True),
        sa.Column("caller_user_id", sa.String(length=36), nullable=True),
        sa.Column("purpose", sa.String(length=40), nullable=False),
        sa.Column("related_id", sa.String(length=36), nullable=True),
        sa.Column("streamed", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=40), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["model_config_id"], ["model_configs.id"]),
        sa.ForeignKeyConstraint(["caller_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_model_call_logs_model_config_id", "model_call_logs", ["model_config_id"])
    op.create_index("ix_model_call_logs_caller_user_id", "model_call_logs", ["caller_user_id"])
    op.create_index("ix_model_call_logs_config_created", "model_call_logs", ["model_config_id", "started_at"])


def downgrade() -> None:
    op.drop_index("ix_model_call_logs_config_created", table_name="model_call_logs")
    op.drop_index("ix_model_call_logs_caller_user_id", table_name="model_call_logs")
    op.drop_index("ix_model_call_logs_model_config_id", table_name="model_call_logs")
    op.drop_table("model_call_logs")
    op.drop_index("ix_model_configs_is_default", table_name="model_configs")
    op.drop_table("model_configs")
