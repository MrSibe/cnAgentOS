"""merge phase1 model_engine and activate system functions

Revision ID: 0005_merge_heads
Revises: 0002_phase1_model_engine, 0004_activate_system_functions
Create Date: 2026-05-28
"""

from alembic import op


revision = "0005_merge_heads"
down_revision = ("0002_phase1_model_engine", "0004_activate_system_functions")
branch_labels = None
depends_on = None


def upgrade() -> None:
    # System functions already activated by 0004, nothing additional needed here
    # This merge revision exists to reconcile the divergent branches
    pass


def downgrade() -> None:
    pass
