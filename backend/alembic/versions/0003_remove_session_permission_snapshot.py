"""remove stale permission snapshot from auth sessions

Revision ID: 0003_remove_session_perm
Revises: 0002_auth_session_permissions
Create Date: 2026-05-27
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_remove_session_perm"
down_revision = "0002_auth_session_permissions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("auth_sessions", "permissions")


def downgrade() -> None:
    op.add_column("auth_sessions", sa.Column("permissions", sa.JSON(), nullable=True))
