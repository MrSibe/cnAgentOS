"""add phase 6 chat tables (contacts, friend_requests, conversations, messages)

Revision ID: 0010_phase6_chat
Revises: 0009_phase3_qa_navigation
Create Date: 2026-05-31
"""

from alembic import op
import sqlalchemy as sa


revision = "0010_phase6_chat"
down_revision = "0009_phase3_qa_navigation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- contacts ---
    op.create_table(
        "contacts",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("contact_id", sa.String(36), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("remark", sa.String(120), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_contacts_user_id", "contacts", ["user_id"])
    op.create_index("ix_contacts_contact_id", "contacts", ["contact_id"])

    # --- friend_requests ---
    op.create_table(
        "friend_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("from_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("to_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("message", sa.String(500), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_friend_requests_from", "friend_requests", ["from_user_id", "status"])
    op.create_index("ix_friend_requests_to", "friend_requests", ["to_user_id", "status"])

    # --- conversations ---
    op.create_table(
        "conversations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
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
    op.create_index("ix_conversations_created_by", "conversations", ["created_by"])

    # --- conversation_members ---
    op.create_table(
        "conversation_members",
        sa.Column(
            "conversation_id", sa.String(36), sa.ForeignKey("conversations.id"),
            primary_key=True,
        ),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id"), primary_key=True,
        ),
        sa.Column("role", sa.String(20), nullable=False, server_default="member"),
        sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "joined_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_conv_members_conv", "conversation_members", ["conversation_id"])
    op.create_index("ix_conv_members_user", "conversation_members", ["user_id"])

    # --- file_blobs (Phase 7 ready) ---
    op.create_table(
        "file_blobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("mime_type", sa.String(127), nullable=False),
        sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column("storage_path", sa.String(1024), nullable=False),
        sa.Column("ref_count", sa.Integer, nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # --- files (Phase 7 ready) ---
    op.create_table(
        "files",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("blob_id", sa.String(36), sa.ForeignKey("file_blobs.id"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("uploaded_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_files_uploaded_by", "files", ["uploaded_by"])

    # --- messages ---
    op.create_table(
        "messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "conversation_id", sa.String(36), sa.ForeignKey("conversations.id"),
            nullable=False,
        ),
        sa.Column("sender_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("content_type", sa.String(20), nullable=False, server_default="text"),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("reply_to_id", sa.String(36), sa.ForeignKey("messages.id"), nullable=True),
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
        "ix_messages_conversation_created", "messages",
        ["conversation_id", "created_at"],
    )
    op.create_index("ix_messages_sender", "messages", ["sender_id"])

    # --- message_read_receipts ---
    op.create_table(
        "message_read_receipts",
        sa.Column(
            "message_id", sa.String(36), sa.ForeignKey("messages.id"), primary_key=True,
        ),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id"), primary_key=True,
        ),
        sa.Column(
            "read_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_read_receipts_user", "message_read_receipts", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_files_uploaded_by", table_name="files")
    op.drop_table("files")
    op.drop_table("file_blobs")
    op.drop_index("ix_read_receipts_user", table_name="message_read_receipts")
    op.drop_table("message_read_receipts")
    op.drop_index("ix_messages_sender", table_name="messages")
    op.drop_index("ix_messages_conversation_created", table_name="messages")
    op.drop_table("messages")
    op.drop_index("ix_conv_members_user", table_name="conversation_members")
    op.drop_index("ix_conv_members_conv", table_name="conversation_members")
    op.drop_table("conversation_members")
    op.drop_index("ix_conversations_created_by", table_name="conversations")
    op.drop_table("conversations")
    op.drop_index("ix_friend_requests_to", table_name="friend_requests")
    op.drop_index("ix_friend_requests_from", table_name="friend_requests")
    op.drop_table("friend_requests")
    op.drop_index("ix_contacts_contact_id", table_name="contacts")
    op.drop_index("ix_contacts_user_id", table_name="contacts")
    op.drop_table("contacts")
