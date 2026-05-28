"""add phase 2 watch and data navigation entries

Revision ID: 0006_phase2_navigation_entries
Revises: 0005_merge_heads
Create Date: 2026-05-28
"""

from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision = "0006_phase2_navigation_entries"
down_revision = "0005_merge_heads"
branch_labels = None
depends_on = None


FUNCTIONS = [
    ("watch", "智能瞭望", None, None, "file-search", 20, None),
    (
        "watch_sources",
        "数据源与规则",
        "watch",
        "/admin/watch-sources",
        "file-search",
        10,
        "watch.sources.manage",
    ),
    (
        "watch_tasks",
        "采集任务",
        "watch",
        "/admin/collection-tasks",
        "activity",
        20,
        "watch.tasks.view",
    ),
    ("data", "数据仓库", None, None, "activity", 30, None),
    (
        "data_items",
        "内容治理",
        "data",
        "/admin/knowledge-items",
        "file-search",
        10,
        "data.items.view",
    ),
]


def upgrade() -> None:
    bind = op.get_bind()
    function_ids: dict[str, str] = {}

    for code, name, parent_code, route_path, icon, sort_order, permission_code in FUNCTIONS:
        existing_id = bind.execute(
            sa.text("SELECT id FROM functions WHERE code = :code"),
            {"code": code},
        ).scalar_one_or_none()
        parent_id = function_ids.get(parent_code)

        if existing_id is None:
            existing_id = str(uuid4())
            bind.execute(
                sa.text(
                    """
                    INSERT INTO functions (
                        id, code, name, parent_id, route_path, icon, sort_order,
                        required_permission_code, status, is_system, created_at, updated_at
                    )
                    VALUES (
                        :id, :code, :name, :parent_id, :route_path, :icon, :sort_order,
                        :permission_code, 'active', TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                    """
                ),
                {
                    "id": existing_id,
                    "code": code,
                    "name": name,
                    "parent_id": parent_id,
                    "route_path": route_path,
                    "icon": icon,
                    "sort_order": sort_order,
                    "permission_code": permission_code,
                },
            )
        else:
            bind.execute(
                sa.text(
                    """
                    UPDATE functions
                    SET
                        name = :name,
                        parent_id = :parent_id,
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
                {
                    "code": code,
                    "name": name,
                    "parent_id": parent_id,
                    "route_path": route_path,
                    "icon": icon,
                    "sort_order": sort_order,
                    "permission_code": permission_code,
                },
            )

        function_ids[code] = existing_id


def downgrade() -> None:
    op.execute("DELETE FROM functions WHERE code IN ('watch_sources', 'watch_tasks', 'data_items')")
    op.execute("DELETE FROM functions WHERE code IN ('watch', 'data')")
