"""create watch and data tables

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
    op.create_table(
        "watch_sources",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("entry_url", sa.String(length=2048), nullable=False),
        sa.Column("allowed_hosts", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("auth_ciphertext", sa.Text(), nullable=True),
        sa.Column("auth_mask", sa.String(length=120), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_watch_sources_status", "watch_sources", ["status"])
    op.create_index("ix_watch_sources_source_type", "watch_sources", ["source_type"])

    op.create_table(
        "watch_rules",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("request_method", sa.String(length=10), nullable=False),
        sa.Column("request_headers", postgresql.JSONB(), nullable=True),
        sa.Column("request_params", postgresql.JSONB(), nullable=True),
        sa.Column("extractor_type", sa.String(length=20), nullable=False),
        sa.Column("extractor_config", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["watch_sources.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_watch_rules_source_status", "watch_rules", ["source_id", "status"])

    op.create_table(
        "collection_tasks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("trigger_type", sa.String(length=20), nullable=False),
        sa.Column("source_count", sa.Integer(), nullable=False),
        sa.Column("item_success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("item_failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failure_summary", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_collection_tasks_status_created", "collection_tasks", ["status", "created_at"])

    op.create_table(
        "collection_task_sources",
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("source_id", sa.String(length=36), nullable=False),
        sa.Column("rule_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("failure_summary", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["task_id"], ["collection_tasks.id"]),
        sa.ForeignKeyConstraint(["source_id"], ["watch_sources.id"]),
        sa.ForeignKeyConstraint(["rule_id"], ["watch_rules.id"]),
        sa.PrimaryKeyConstraint("task_id", "source_id"),
    )

    op.create_table(
        "knowledge_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source_id", sa.String(length=36), nullable=True),
        sa.Column("task_id", sa.String(length=36), nullable=True),
        sa.Column("external_key", sa.String(length=512), nullable=True),
        sa.Column("canonical_url", sa.String(length=2048), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("reviewed_by", sa.String(length=36), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["watch_sources.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["collection_tasks.id"]),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_items_source_status_collected", "knowledge_items", ["source_id", "status", "collected_at"])
    op.create_index("ix_knowledge_items_content_hash", "knowledge_items", ["content_hash"])
    op.create_index("ix_knowledge_items_external_key", "knowledge_items", ["source_id", "external_key"])

    op.create_table(
        "collection_task_items",
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("knowledge_item_id", sa.String(length=36), nullable=False),
        sa.Column("source_id", sa.String(length=36), nullable=True),
        sa.Column("ingest_result", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["collection_tasks.id"]),
        sa.ForeignKeyConstraint(["knowledge_item_id"], ["knowledge_items.id"]),
        sa.ForeignKeyConstraint(["source_id"], ["watch_sources.id"]),
        sa.PrimaryKeyConstraint("task_id", "knowledge_item_id"),
    )
    op.create_index("ix_collection_task_items_knowledge_created", "collection_task_items", ["knowledge_item_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_collection_task_items_knowledge_created", table_name="collection_task_items")
    op.drop_table("collection_task_items")
    op.drop_index("ix_knowledge_items_external_key", table_name="knowledge_items")
    op.drop_index("ix_knowledge_items_content_hash", table_name="knowledge_items")
    op.drop_index("ix_knowledge_items_source_status_collected", table_name="knowledge_items")
    op.drop_table("knowledge_items")
    op.drop_table("collection_task_sources")
    op.drop_index("ix_collection_tasks_status_created", table_name="collection_tasks")
    op.drop_table("collection_tasks")
    op.drop_index("ix_watch_rules_source_status", table_name="watch_rules")
    op.drop_table("watch_rules")
    op.drop_index("ix_watch_sources_source_type", table_name="watch_sources")
    op.drop_index("ix_watch_sources_status", table_name="watch_sources")
    op.drop_table("watch_sources")
