"""Phase 2B watch sources, rules, collection tasks and knowledge items

Revision ID: 0006_phase2_watch_data
Revises: 0005_merge_heads
Create Date: 2026-05-28

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006_phase2_watch_data"
down_revision = "0005_merge_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Watch Sources table
    op.create_table(
        "watch_sources",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("entry_url", sa.String(2048), nullable=False),
        sa.Column("allowed_hosts", postgresql.JSON, nullable=False),
        sa.Column("status", sa.String(20), default="disabled"),
        sa.Column("auth_ciphertext", sa.Text, nullable=True),
        sa.Column("auth_mask", sa.String(120), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )

    # Watch Rules table
    op.create_table(
        "watch_rules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_id", sa.String(36), sa.ForeignKey("watch_sources.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("request_method", sa.String(10), nullable=False),
        sa.Column("request_headers", postgresql.JSON, nullable=True),
        sa.Column("request_params", postgresql.JSON, nullable=True),
        sa.Column("extractor_type", sa.String(20), nullable=False),
        sa.Column("extractor_config", postgresql.JSON, nullable=False),
        sa.Column("status", sa.String(20), default="disabled"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )
    op.create_index("ix_watch_rules_source_id", "watch_rules", ["source_id"])

    # Collection Tasks table
    op.create_table(
        "collection_tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("status", sa.String(20), default="pending"),
        sa.Column("trigger_type", sa.String(20), default="manual"),
        sa.Column("source_count", sa.Integer, default=0),
        sa.Column("item_success_count", sa.Integer, default=0),
        sa.Column("item_failure_count", sa.Integer, default=0),
        sa.Column("failure_summary", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Collection Task Sources junction table
    op.create_table(
        "collection_task_sources",
        sa.Column("task_id", sa.String(36), sa.ForeignKey("collection_tasks.id"), primary_key=True),
        sa.Column("source_id", sa.String(36), sa.ForeignKey("watch_sources.id"), primary_key=True),
        sa.Column("rule_id", sa.String(36), sa.ForeignKey("watch_rules.id"), nullable=False),
        sa.Column("status", sa.String(20), default="pending"),
        sa.Column("failure_summary", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Knowledge Items table
    op.create_table(
        "knowledge_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_id", sa.String(36), sa.ForeignKey("watch_sources.id"), nullable=True),
        sa.Column("task_id", sa.String(36), sa.ForeignKey("collection_tasks.id"), nullable=True),
        sa.Column("external_key", sa.String(512), nullable=True),
        sa.Column("canonical_url", sa.String(2048), nullable=True),
        sa.Column("title", sa.String(512), nullable=True),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), default="available"),
        sa.Column("reviewed_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )
    op.create_index("ix_knowledge_items_content_hash", "knowledge_items", ["content_hash"])

    # Collection Task Items junction table
    op.create_table(
        "collection_task_items",
        sa.Column("task_id", sa.String(36), sa.ForeignKey("collection_tasks.id"), primary_key=True),
        sa.Column("knowledge_item_id", sa.String(36), sa.ForeignKey("knowledge_items.id"), primary_key=True),
        sa.Column("source_id", sa.String(36), sa.ForeignKey("watch_sources.id"), nullable=True),
        sa.Column("ingest_result", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("collection_task_items")
    op.drop_table("knowledge_items")
    op.drop_table("collection_task_sources")
    op.drop_table("collection_tasks")
    op.drop_table("watch_rules")
    op.drop_table("watch_sources")
