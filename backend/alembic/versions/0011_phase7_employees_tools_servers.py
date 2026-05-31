"""add phase 7 tables (digital_employees, tools, chat_servers, group enhancements)

Revision ID: 0011_phase7_employees_tools_servers
Revises: 0010_phase6_chat
Create Date: 2026-05-31
"""

from alembic import op
import sqlalchemy as sa


revision = "0011_phase7_employees_tools_servers"
down_revision = "0010_phase6_chat"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- extend existing tables ---
    op.add_column(
        "conversations",
        sa.Column("is_disbanded", sa.Boolean, nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "conversation_members",
        sa.Column("banned_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "conversation_members",
        sa.Column("banned_by", sa.String(36), nullable=True),
    )

    # --- digital_employees ---
    op.create_table(
        "digital_employees",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(60), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("avatar", sa.String(512), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("system_prompt", sa.Text, nullable=False),
        sa.Column(
            "model_config_id", sa.String(36),
            sa.ForeignKey("model_configs.id"), nullable=True,
        ),
        sa.Column("trigger_type", sa.String(20), nullable=False, server_default="mention"),
        sa.Column("max_turns", sa.Integer, nullable=False, server_default="20"),
        sa.Column("status", sa.String(20), nullable=False, server_default="disabled"),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_digital_employees_code", "digital_employees", ["code"])

    # --- tools ---
    op.create_table(
        "tools",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(60), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("tool_type", sa.String(30), nullable=False),
        sa.Column("config", sa.JSON, nullable=False),
        sa.Column("config_ciphertext", sa.Text, nullable=True),
        sa.Column("config_mask", sa.String(120), nullable=True),
        sa.Column("invocation_limit", sa.Integer, nullable=False, server_default="100"),
        sa.Column(
            "invocation_window_seconds", sa.Integer,
            nullable=False, server_default="3600",
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="disabled"),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_tools_code", "tools", ["code"])

    # --- employee_tool_bindings ---
    op.create_table(
        "employee_tool_bindings",
        sa.Column(
            "employee_id", sa.String(36),
            sa.ForeignKey("digital_employees.id"), primary_key=True,
        ),
        sa.Column(
            "tool_id", sa.String(36), sa.ForeignKey("tools.id"), primary_key=True,
        ),
        sa.Column("binding_config", sa.JSON, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # --- tool_invocation_logs ---
    op.create_table(
        "tool_invocation_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tool_id", sa.String(36), sa.ForeignKey("tools.id"), nullable=False),
        sa.Column(
            "employee_id", sa.String(36),
            sa.ForeignKey("digital_employees.id"), nullable=True,
        ),
        sa.Column(
            "message_id", sa.String(36),
            sa.ForeignKey("messages.id"), nullable=True,
        ),
        sa.Column("caller_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("input_params", sa.JSON, nullable=True),
        sa.Column("output_summary", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error_code", sa.String(40), nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_tool_invocation_tool", "tool_invocation_logs",
        ["tool_id", "created_at"],
    )
    op.create_index(
        "ix_tool_invocation_employee", "tool_invocation_logs",
        ["employee_id", "created_at"],
    )

    # --- chat_servers ---
    op.create_table(
        "chat_servers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("base_url", sa.String(512), nullable=False),
        sa.Column("health_check_url", sa.String(512), nullable=True),
        sa.Column("auth_ciphertext", sa.Text, nullable=True),
        sa.Column("auth_mask", sa.String(120), nullable=True),
        sa.Column("priority", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="disabled"),
        sa.Column("last_health_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_health_check_result", sa.String(20), nullable=True),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # --- group_announcements ---
    op.create_table(
        "group_announcements",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "conversation_id", sa.String(36),
            sa.ForeignKey("conversations.id"), nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("is_pinned", sa.Boolean, nullable=False, server_default=sa.text("0")),
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
        "ix_group_announcements_conv", "group_announcements",
        ["conversation_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_group_announcements_conv", table_name="group_announcements")
    op.drop_table("group_announcements")
    op.drop_table("chat_servers")
    op.drop_index("ix_tool_invocation_employee", table_name="tool_invocation_logs")
    op.drop_index("ix_tool_invocation_tool", table_name="tool_invocation_logs")
    op.drop_table("tool_invocation_logs")
    op.drop_table("employee_tool_bindings")
    op.drop_index("ix_tools_code", table_name="tools")
    op.drop_table("tools")
    op.drop_index("ix_digital_employees_code", table_name="digital_employees")
    op.drop_table("digital_employees")
    op.drop_column("conversation_members", "banned_by")
    op.drop_column("conversation_members", "banned_at")
    op.drop_column("conversations", "is_disbanded")
