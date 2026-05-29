"""add phase 3 question answering navigation entry

Revision ID: 0009_phase3_qa_navigation
Revises: 0008_phase3_qa_security
Create Date: 2026-05-29
"""

from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision = "0009_phase3_qa_navigation"
down_revision = "0008_phase3_qa_security"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    existing_id = bind.execute(
        sa.text("SELECT id FROM functions WHERE code = :code"),
        {"code": "qa"},
    ).scalar_one_or_none()
    values = {
        "id": existing_id or str(uuid4()),
        "code": "qa",
        "name": "智能问数",
        "route_path": "/qa",
        "icon": "sparkles",
        "sort_order": 40,
        "permission_code": "qa.use",
    }
    if existing_id is None:
        bind.execute(
            sa.text(
                """
                INSERT INTO functions (
                    id, code, name, parent_id, route_path, icon, sort_order,
                    required_permission_code, status, is_system, created_at, updated_at
                )
                VALUES (
                    :id, :code, :name, NULL, :route_path, :icon, :sort_order,
                    :permission_code, 'active', TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                """
            ),
            values,
        )
    else:
        bind.execute(
            sa.text(
                """
                UPDATE functions
                SET
                    name = :name,
                    parent_id = NULL,
                    route_path = :route_path,
                    icon = :icon,
                    sort_order = :sort_order,
                    required_permission_code = :permission_code,
                    status = 'active',
                    is_system = TRUE,
                    updated_at = CURRENT_TIMESTAMP
                WHERE code = :code
                """
            ),
            values,
        )


def downgrade() -> None:
    op.execute("DELETE FROM functions WHERE code = 'qa'")
