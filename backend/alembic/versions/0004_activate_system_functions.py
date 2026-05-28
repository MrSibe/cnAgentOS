"""activate system functions for navigation visibility

Revision ID: 0004_activate_system_functions
Revises: 0003_remove_session_permission_snapshot
Create Date: 2026-05-27
"""

from alembic import op

revision = "0004_activate_system_functions"
down_revision = "0003_remove_session_perm"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE functions SET status = 'active' WHERE is_system = TRUE")


def downgrade() -> None:
    op.execute("UPDATE functions SET status = 'disabled' WHERE is_system = TRUE")
