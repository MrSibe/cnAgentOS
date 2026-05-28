"""add permissions JSON column to auth_sessions

Revision ID: 0002_auth_session_permissions
Revises: 0001_phase1_platform
Create Date: 2026-05-27
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_auth_session_permissions"
down_revision = "0001_phase1_platform"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("auth_sessions", sa.Column("permissions", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("auth_sessions", "permissions")
