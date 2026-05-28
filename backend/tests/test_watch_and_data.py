"""Integration tests for watch and data module."""

import pytest


async def test_watch_source_crud(client, admin_session):
    """Test basic CRUD operations for watch sources."""
    created = await client.post(
        "/api/v1/admin/watch-sources",
        headers={"X-CSRF-Token": admin_session},
        json={
            "name": "测试新闻源",
            "source_type": "web_page",
            "entry_url": "https://news.example.com/search",
            "allowed_hosts": ["news.example.com"],
            "description": "用于测试的新闻源",
        },
    )
    assert created.status_code == 201
    data = created.json()["data"]
    source_id = data["id"]
    assert data["name"] == "测试新闻源"
    assert data["status"] == "disabled"
    assert data["auth_configured"] is False

    single = await client.get(f"/api/v1/admin/watch-sources/{source_id}")
    assert single.status_code == 200
    assert single.json()["data"]["id"] == source_id

    updated = await client.patch(
        f"/api/v1/admin/watch-sources/{source_id}",
        headers={"X-CSRF-Token": admin_session},
        json={"name": "测试新闻源改"},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["name"] == "测试新闻源改"


async def test_watch_source_with_auth(client, admin_session):
    """Test watch source creation with authentication config."""
    created = await client.post(
        "/api/v1/admin/watch-sources",
        headers={"X-CSRF-Token": admin_session},
        json={
            "name": "需要认证的数据源",
            "source_type": "web_api",
            "entry_url": "https://api.example.com/data",
            "allowed_hosts": ["api.example.com"],
            "auth_config": {"headers": {"Authorization": "Bearer secret-key"}},
            "description": "需要认证的 API",
        },
    )
    assert created.status_code == 201
    data = created.json()["data"]
    assert data["auth_configured"] is True
    assert data["auth_mask"] == "****已配置"

    body_str = created.text
    assert "secret-key" not in body_str


async def test_watch_source_ssrf_validation(client, admin_session):
    """Test SSRF protection for watch sources."""
    resp = await client.post(
        "/api/v1/admin/watch-sources",
        headers={"X-CSRF-Token": admin_session},
        json={
            "name": "非法数据源",
            "source_type": "web_page",
            "entry_url": "http://169.254.169.254/latest/meta-data/",
            "allowed_hosts": ["169.254.169.254"],
            "description": "尝试 SSRF 攻击",
        },
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "SOURCE_UNSAFE"

    resp_local = await client.post(
        "/api/v1/admin/watch-sources",
        headers={"X-CSRF-Token": admin_session},
        json={
            "name": "内网数据源",
            "source_type": "web_page",
            "entry_url": "https://192.168.1.1/admin",
            "allowed_hosts": ["192.168.1.1"],
            "description": "尝试访问内网",
        },
    )
    assert resp_local.status_code == 422
    assert resp_local.json()["error"]["code"] == "SOURCE_UNSAFE"


async def test_watch_source_list_pagination(client, admin_session):
    """Test watch source listing with pagination and filters."""
    await client.post(
        "/api/v1/admin/watch-sources",
        headers={"X-CSRF-Token": admin_session},
        json={
            "name": "数据源甲",
            "source_type": "web_page",
            "entry_url": "https://site-a.example.com/",
            "allowed_hosts": ["site-a.example.com"],
        },
    )
    await client.post(
        "/api/v1/admin/watch-sources",
        headers={"X-CSRF-Token": admin_session},
        json={
            "name": "数据源乙",
            "source_type": "web_api",
            "entry_url": "https://api.example.com/v1/data",
            "allowed_hosts": ["api.example.com"],
        },
    )

    sources = await client.get("/api/v1/admin/watch-sources")
    assert sources.status_code == 200
    assert sources.json()["meta"]["total"] >= 2

    paged = await client.get("/api/v1/admin/watch-sources", params={"page": 1, "page_size": 1})
    assert paged.status_code == 200
    assert len(paged.json()["data"]) == 1

    search = await client.get("/api/v1/admin/watch-sources", params={"q": "数据源甲"})
    assert search.status_code == 200
    assert any(s["name"] == "数据源甲" for s in search.json()["data"])

    by_type = await client.get("/api/v1/admin/watch-sources", params={"source_type": "web_page"})
    assert by_type.status_code == 200


async def test_watch_rule_crud(client, admin_session):
    """Test watch rule CRUD operations."""
    source = await client.post(
        "/api/v1/admin/watch-sources",
        headers={"X-CSRF-Token": admin_session},
        json={
            "name": "规则测试源",
            "source_type": "web_page",
            "entry_url": "https://test.example.com/",
            "allowed_hosts": ["test.example.com"],
        },
    )
    source_id = source.json()["data"]["id"]

    rule = await client.post(
        f"/api/v1/admin/watch-sources/{source_id}/rules",
        headers={"X-CSRF-Token": admin_session},
        json={
            "name": "新闻列表规则",
            "request_method": "GET",
            "request_params": {"keyword": "test"},
            "extractor_type": "html",
            "extractor_config": {
                "item_selector": ".news-item",
                "title_selector": ".title",
            },
        },
    )
    assert rule.status_code == 201
    data = rule.json()["data"]
    rule_id = data["id"]
    assert data["status"] == "disabled"
    assert data["extractor_type"] == "html"

    rules = await client.get(f"/api/v1/admin/watch-sources/{source_id}/rules")
    assert rules.status_code == 200
    assert len(rules.json()["data"]) >= 1

    updated = await client.patch(
        f"/api/v1/admin/watch-rules/{rule_id}",
        headers={"X-CSRF-Token": admin_session},
        json={"name": "规则改名"},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["name"] == "规则改名"


async def test_watch_rule_not_found(client, admin_session):
    """Test watch rule not found handling."""
    resp = await client.get("/api/v1/admin/watch-sources/nonexistent/rules")
    assert resp.status_code == 404

    resp = await client.patch(
        "/api/v1/admin/watch-rules/nonexistent-id",
        headers={"X-CSRF-Token": admin_session},
        json={"name": "改名"},
    )
    assert resp.status_code == 404


async def test_collection_task_creation_and_listing(client, admin_session):
    """Test collection task creation and listing."""
    source = await client.post(
        "/api/v1/admin/watch-sources",
        headers={"X-CSRF-Token": admin_session},
        json={
            "name": "任务测试源",
            "source_type": "web_page",
            "entry_url": "https://task.example.com/",
            "allowed_hosts": ["task.example.com"],
        },
    )
    source_id = source.json()["data"]["id"]

    rule = await client.post(
        f"/api/v1/admin/watch-sources/{source_id}/rules",
        headers={"X-CSRF-Token": admin_session},
        json={
            "name": "任务测试规则",
            "request_method": "GET",
            "extractor_type": "html",
            "extractor_config": {"item_selector": "a"},
        },
    )
    rule_id = rule.json()["data"]["id"]

    activate_source = await client.patch(
        f"/api/v1/admin/watch-sources/{source_id}/status",
        headers={"X-CSRF-Token": admin_session},
        json={"status": "active"},
    )
    assert activate_source.status_code == 200

    activate_rule = await client.patch(
        f"/api/v1/admin/watch-rules/{rule_id}",
        headers={"X-CSRF-Token": admin_session},
        json={"status": "active"},
    )
    assert activate_rule.status_code == 200

    task = await client.post(
        "/api/v1/admin/collection-tasks",
        headers={"X-CSRF-Token": admin_session},
        json={
            "targets": [
                {"source_id": source_id, "rule_id": rule_id, "variables": {"query": "test"}}
            ]
        },
    )
    assert task.status_code == 202
    task_data = task.json()["data"]
    task_id = task_data["id"]
    assert task_data["status"] == "pending"

    tasks = await client.get("/api/v1/admin/collection-tasks")
    assert tasks.status_code == 200
    assert tasks.json()["meta"]["total"] >= 1

    single_task = await client.get(f"/api/v1/admin/collection-tasks/{task_id}")
    assert single_task.status_code == 200
    assert single_task.json()["data"]["id"] == task_id


async def test_collection_task_cancel(client, admin_session):
    """Test collection task cancellation."""
    source = await client.post(
        "/api/v1/admin/watch-sources",
        headers={"X-CSRF-Token": admin_session},
        json={
            "name": "取消测试源",
            "source_type": "web_page",
            "entry_url": "https://cancel.example.com/",
            "allowed_hosts": ["cancel.example.com"],
        },
    )
    source_id = source.json()["data"]["id"]

    rule = await client.post(
        f"/api/v1/admin/watch-sources/{source_id}/rules",
        headers={"X-CSRF-Token": admin_session},
        json={
            "name": "取消测试规则",
            "request_method": "GET",
            "extractor_type": "html",
            "extractor_config": {"item_selector": "a"},
        },
    )
    rule_id = rule.json()["data"]["id"]

    await client.patch(
        f"/api/v1/admin/watch-sources/{source_id}/status",
        headers={"X-CSRF-Token": admin_session},
        json={"status": "active"},
    )
    await client.patch(
        f"/api/v1/admin/watch-rules/{rule_id}",
        headers={"X-CSRF-Token": admin_session},
        json={"status": "active"},
    )

    task = await client.post(
        "/api/v1/admin/collection-tasks",
        headers={"X-CSRF-Token": admin_session},
        json={"targets": [{"source_id": source_id, "rule_id": rule_id}]},
    )
    task_id = task.json()["data"]["id"]

    cancelled = await client.post(
        f"/api/v1/admin/collection-tasks/{task_id}/cancel",
        headers={"X-CSRF-Token": admin_session},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["data"]["status"] == "cancelled"


async def test_source_activation_requires_active_rule(client, admin_session):
    """Test that source activation requires at least one active rule."""
    source = await client.post(
        "/api/v1/admin/watch-sources",
        headers={"X-CSRF-Token": admin_session},
        json={
            "name": "无规则数据源",
            "source_type": "web_page",
            "entry_url": "https://norule.example.com/",
            "allowed_hosts": ["norule.example.com"],
        },
    )
    source_id = source.json()["data"]["id"]

    activate = await client.patch(
        f"/api/v1/admin/watch-sources/{source_id}/status",
        headers={"X-CSRF-Token": admin_session},
        json={"status": "active"},
    )
    assert activate.status_code == 409
    assert activate.json()["error"]["code"] == "INVALID_STATE"


async def test_knowledge_items_listing(client, admin_session):
    """Test knowledge items listing and filtering."""
    items = await client.get("/api/v1/admin/knowledge-items")
    assert items.status_code == 200
    assert "data" in items.json()
    assert "meta" in items.json()


async def test_knowledge_items_requires_permission(client, app):
    """Test that knowledge items require proper permissions."""
    from httpx import ASGITransport, AsyncClient

    resp = await client.post(
        "/api/v1/admin/users",
        headers={"X-CSRF-Token": admin_session},
        json={
            "username": "no_data_perm_user",
            "display_name": "无数据权限用户",
            "password": "Nodata-password-123",
            "role_ids": [],
        },
    )
    assert resp.status_code == 201

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as no_perm_client:
        login_resp = await no_perm_client.post(
            "/api/v1/auth/login",
            json={"username": "no_data_perm_user", "password": "Nodata-password-123"},
        )
        assert login_resp.status_code == 200

        view_forbidden = await no_perm_client.get("/api/v1/admin/knowledge-items")
        assert view_forbidden.status_code == 403


async def test_task_requires_active_source_and_rule(client, admin_session):
    """Test that creating a task requires active source and rule."""
    source = await client.post(
        "/api/v1/admin/watch-sources",
        headers={"X-CSRF-Token": admin_session},
        json={
            "name": "停用数据源",
            "source_type": "web_page",
            "entry_url": "https://inactive.example.com/",
            "allowed_hosts": ["inactive.example.com"],
        },
    )
    source_id = source.json()["data"]["id"]

    rule = await client.post(
        f"/api/v1/admin/watch-sources/{source_id}/rules",
        headers={"X-CSRF-Token": admin_session},
        json={
            "name": "停用规则",
            "request_method": "GET",
            "extractor_type": "html",
            "extractor_config": {"item_selector": "a"},
        },
    )
    rule_id = rule.json()["data"]["id"]

    task = await client.post(
        "/api/v1/admin/collection-tasks",
        headers={"X-CSRF-Token": admin_session},
        json={"targets": [{"source_id": source_id, "rule_id": rule_id}]},
    )
    assert task.status_code == 409
    assert task.json()["error"]["code"] == "INVALID_STATE"


async def test_watch_permission_enforcement(client, app, admin_session):
    """Test that watch operations require proper permissions."""
    from httpx import ASGITransport, AsyncClient

    permissions = await client.get("/api/v1/admin/permissions")
    permissions_data = permissions.json()["data"]
    watch_manage_perm = next(p for p in permissions_data if p["code"] == "watch.sources.manage")

    viewer_role = await client.post(
        "/api/v1/admin/roles",
        headers={"X-CSRF-Token": admin_session},
        json={
            "code": "watch_viewer_role",
            "name": "瞭望查看者",
            "permission_ids": [],
        },
    )
    viewer_role_id = viewer_role.json()["data"]["id"]

    viewer_user = await client.post(
        "/api/v1/admin/users",
        headers={"X-CSRF-Token": admin_session},
        json={
            "username": "watch_viewer_user",
            "display_name": "瞭望观察者",
            "password": "Watchview-password-123",
            "role_ids": [viewer_role_id],
        },
    )
    assert viewer_user.status_code == 201

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as viewer_client:
        login_resp = await viewer_client.post(
            "/api/v1/auth/login",
            json={"username": "watch_viewer_user", "password": "Watchview-password-123"},
        )
        assert login_resp.status_code == 200
        viewer_csrf = login_resp.json()["data"]["csrf_token"]

        create_forbidden = await viewer_client.post(
            "/api/v1/admin/watch-sources",
            headers={"X-CSRF-Token": viewer_csrf},
            json={
                "name": "非法创建",
                "source_type": "web_page",
                "entry_url": "https://test.example.com/",
                "allowed_hosts": ["test.example.com"],
            },
        )
        assert create_forbidden.status_code == 403
        assert create_forbidden.json()["error"]["code"] == "PERMISSION_DENIED"
