import json

from httpx import ASGITransport, AsyncClient

from conftest import ADMIN_PASSWORD


async def test_login_me_and_csrf_enforcement(client, admin_session):
    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["data"]["csrf_token"] == admin_session
    assert "users.manage" in me.json()["data"]["permissions"]

    rejected = await client.post(
        "/api/v1/admin/users",
        json={
            "username": "analyst",
            "display_name": "分析员",
            "password": "Analyst-password-123",
            "role_ids": [],
        },
    )
    assert rejected.status_code == 403
    assert rejected.json()["error"]["code"] == "CSRF_INVALID"

    missing = await client.get("/api/v1/admin/not-a-resource")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "NOT_FOUND"


async def test_user_creation_password_reset_and_session_revocation(client, admin_session, app):
    created = await client.post(
        "/api/v1/admin/users",
        headers={"X-CSRF-Token": admin_session},
        json={
            "username": "analyst",
            "display_name": "分析员",
            "password": "Analyst-password-123",
            "role_ids": [],
        },
    )
    assert created.status_code == 201
    assert "password" not in json.dumps(created.json())
    user_id = created.json()["data"]["id"]

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as analyst:
        login = await analyst.post(
            "/api/v1/auth/login",
            json={"username": "analyst", "password": "Analyst-password-123"},
        )
        assert login.status_code == 200
        reset = await client.post(
            f"/api/v1/admin/users/{user_id}/password-reset",
            headers={"X-CSRF-Token": admin_session},
            json={"new_password": "New-analyst-password-123"},
        )
        assert reset.status_code == 204
        invalidated = await analyst.get("/api/v1/auth/me")
        assert invalidated.status_code == 401

    relogin = await client.post(
        "/api/v1/auth/login",
        json={"username": "analyst", "password": "New-analyst-password-123"},
    )
    assert relogin.status_code == 200


async def test_system_role_and_last_admin_are_protected(client, admin_session):
    roles = await client.get("/api/v1/admin/roles")
    system_role = next(role for role in roles.json()["data"] if role["code"] == "system_admin")

    disabled_role = await client.patch(
        f"/api/v1/admin/roles/{system_role['id']}",
        headers={"X-CSRF-Token": admin_session},
        json={"status": "disabled"},
    )
    assert disabled_role.status_code == 409
    assert disabled_role.json()["error"]["code"] == "INVALID_STATE"

    me = await client.get("/api/v1/auth/me")
    disabled_admin = await client.patch(
        f"/api/v1/admin/users/{me.json()['data']['id']}/status",
        headers={"X-CSRF-Token": admin_session},
        json={"status": "disabled"},
    )
    assert disabled_admin.status_code == 409

    audit = await client.get("/api/v1/admin/audit-logs")
    assert any(
        item["action"] == "role.updated" and item["result"] == "failed"
        for item in audit.json()["data"]
    )


async def test_navigation_is_filtered_and_audit_is_sanitized(client, admin_session):
    functions = (await client.get("/api/v1/admin/functions")).json()["data"]
    root = next(item for item in functions if item["code"] == "admin")
    users = next(item for item in functions if item["code"] == "admin_users")
    for item in (root, users):
        response = await client.patch(
            f"/api/v1/admin/functions/{item['id']}",
            headers={"X-CSRF-Token": admin_session},
            json={"status": "active"},
        )
        assert response.status_code == 200

    navigation = await client.get("/api/v1/auth/navigation")
    assert navigation.json()["data"][0]["children"][0]["code"] == "admin_users"

    audit = await client.get("/api/v1/admin/audit-logs")
    body = json.dumps(audit.json(), ensure_ascii=False)
    assert audit.status_code == 200
    assert admin_session not in body
    assert ADMIN_PASSWORD not in body
    assert any(
        item["action"] == "function.updated" for item in audit.json()["data"]
    )


async def test_logout_invalidates_session(client, admin_session):
    logout_resp = await client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": admin_session},
    )
    assert logout_resp.status_code == 204
    me_after = await client.get("/api/v1/auth/me")
    assert me_after.status_code == 401


async def test_user_list_pagination_and_filters(client, admin_session):
    users = await client.get("/api/v1/admin/users")
    assert users.status_code == 200
    body = users.json()
    assert body["meta"]["page"] == 1
    assert body["meta"]["total"] >= 1
    for user in body["data"]:
        assert "password" not in json.dumps(user)
        assert "password_hash" not in json.dumps(user)

    paged = await client.get("/api/v1/admin/users", params={"page": 1, "page_size": 1})
    assert paged.status_code == 200
    assert len(paged.json()["data"]) == 1

    search = await client.get("/api/v1/admin/users", params={"q": "root"})
    assert search.status_code == 200
    assert any(u["username"] == "root" for u in search.json()["data"])

    by_status = await client.get("/api/v1/admin/users", params={"status": "disabled"})
    assert by_status.status_code == 200

    invalid_status = await client.get("/api/v1/admin/users", params={"status": "deleted"})
    assert invalid_status.status_code == 400
    assert invalid_status.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_update_user_display_name_and_roles(client, admin_session):
    created = await client.post(
        "/api/v1/admin/users",
        headers={"X-CSRF-Token": admin_session},
        json={
            "username": "editor1",
            "display_name": "编辑器一",
            "password": "Editor-password-123",
            "role_ids": [],
        },
    )
    user_id = created.json()["data"]["id"]

    roles_list = (await client.get("/api/v1/admin/roles")).json()["data"]
    non_system_role = next(
        (r for r in roles_list if r["code"] != "system_admin"), None
    )
    role_id = (
        non_system_role["id"]
        if non_system_role
        else roles_list[0]["id"]
    )

    updated = await client.patch(
        f"/api/v1/admin/users/{user_id}",
        headers={"X-CSRF-Token": admin_session},
        json={"display_name": "编辑器一改", "role_ids": [role_id]},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["display_name"] == "编辑器一改"
    assert len(updated.json()["data"]["roles"]) == 1
    assert updated.json()["data"]["roles"][0]["id"] == role_id

    empty = await client.patch(
        f"/api/v1/admin/users/{user_id}",
        headers={"X-CSRF-Token": admin_session},
        json={},
    )
    assert empty.status_code == 400


async def test_list_permissions(client, admin_session):
    permissions = await client.get("/api/v1/admin/permissions")
    assert permissions.status_code == 200
    data = permissions.json()["data"]
    assert len(data) >= 13
    for perm in data:
        for field in ("id", "code", "name", "module"):
            assert field in perm
    codes = {p["code"] for p in data}
    assert codes >= {
        "users.manage", "roles.manage", "functions.manage",
        "models.view", "models.manage", "models.test",
        "watch.sources.manage", "watch.tasks.run", "watch.tasks.view",
        "data.items.view", "data.items.manage", "qa.use", "audit.view",
    }


async def test_role_crud(client, admin_session):
    permissions = (await client.get("/api/v1/admin/permissions")).json()["data"]
    perm_id = permissions[0]["id"]

    created = await client.post(
        "/api/v1/admin/roles",
        headers={"X-CSRF-Token": admin_session},
        json={
            "code": "analyst_role",
            "name": "分析员角色",
            "description": "只读分析角色",
            "permission_ids": [perm_id],
        },
    )
    assert created.status_code == 201
    role_id = created.json()["data"]["id"]
    assert created.json()["data"]["code"] == "analyst_role"
    assert created.json()["data"]["permissions"] == [permissions[0]["code"]]

    duplicate = await client.post(
        "/api/v1/admin/roles",
        headers={"X-CSRF-Token": admin_session},
        json={
            "code": "analyst_role",
            "name": "重复代码",
            "permission_ids": [],
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "CONFLICT"

    updated = await client.patch(
        f"/api/v1/admin/roles/{role_id}",
        headers={"X-CSRF-Token": admin_session},
        json={"name": "分析员角色改", "description": "更新后描述"},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["name"] == "分析员角色改"
    assert updated.json()["data"]["description"] == "更新后描述"

    deleted = await client.delete(
        f"/api/v1/admin/roles/{role_id}",
        headers={"X-CSRF-Token": admin_session},
    )
    assert deleted.status_code == 204

    missing = await client.delete(
        f"/api/v1/admin/roles/{role_id}",
        headers={"X-CSRF-Token": admin_session},
    )
    assert missing.status_code == 404


async def test_role_delete_rejects_when_assigned(client, admin_session):
    system_role_id = (
        await client.get("/api/v1/admin/roles")
    ).json()["data"][0]["id"]

    res = await client.delete(
        f"/api/v1/admin/roles/{system_role_id}",
        headers={"X-CSRF-Token": admin_session},
    )
    assert res.status_code == 409


async def test_function_crud_and_cycle_guard(client, admin_session):
    created = await client.post(
        "/api/v1/admin/functions",
        headers={"X-CSRF-Token": admin_session},
        json={
            "code": "test_menu",
            "name": "测试菜单",
            "parent_id": None,
            "route_path": "/admin/test",
            "icon": "test",
            "sort_order": 100,
        },
    )
    assert created.status_code == 201
    func_id = created.json()["data"]["id"]
    assert created.json()["data"]["status"] == "disabled"

    duplicate = await client.post(
        "/api/v1/admin/functions",
        headers={"X-CSRF-Token": admin_session},
        json={"code": "test_menu", "name": "重复功能", "sort_order": 0},
    )
    assert duplicate.status_code == 409

    child = await client.post(
        "/api/v1/admin/functions",
        headers={"X-CSRF-Token": admin_session},
        json={
            "code": "test_sub_menu",
            "name": "子菜单",
            "parent_id": func_id,
            "sort_order": 0,
        },
    )
    assert child.status_code == 201
    child_id = child.json()["data"]["id"]

    cycle_resp = await client.patch(
        f"/api/v1/admin/functions/{func_id}",
        headers={"X-CSRF-Token": admin_session},
        json={"parent_id": child_id},
    )
    assert cycle_resp.status_code == 409
    assert cycle_resp.json()["error"]["code"] == "INVALID_STATE"

    delete_parent = await client.delete(
        f"/api/v1/admin/functions/{func_id}",
        headers={"X-CSRF-Token": admin_session},
    )
    assert delete_parent.status_code == 409

    delete_child = await client.delete(
        f"/api/v1/admin/functions/{child_id}",
        headers={"X-CSRF-Token": admin_session},
    )
    assert delete_child.status_code == 204

    enabled = await client.patch(
        f"/api/v1/admin/functions/{func_id}",
        headers={"X-CSRF-Token": admin_session},
        json={"status": "active"},
    )
    assert enabled.status_code == 200

    delete_active = await client.delete(
        f"/api/v1/admin/functions/{func_id}",
        headers={"X-CSRF-Token": admin_session},
    )
    assert delete_active.status_code == 409


async def test_permission_denied_for_non_admin(client, admin_session, app):
    created = await client.post(
        "/api/v1/admin/users",
        headers={"X-CSRF-Token": admin_session},
        json={
            "username": "viewer",
            "display_name": "观察者",
            "password": "Viewer-password-123",
            "role_ids": [],
        },
    )
    assert created.status_code == 201

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as viewer:
        login_resp = await viewer.post(
            "/api/v1/auth/login",
            json={"username": "viewer", "password": "Viewer-password-123"},
        )
        assert login_resp.status_code == 200

        me = await viewer.get("/api/v1/auth/me")
        assert me.status_code == 200
        assert "users.manage" not in me.json()["data"]["permissions"]

        forbidden = await viewer.get("/api/v1/admin/users")
        assert forbidden.status_code == 403
        assert forbidden.json()["error"]["code"] == "PERMISSION_DENIED"

        forbidden_csrf = await viewer.post(
            "/api/v1/admin/roles",
            headers={"X-CSRF-Token": login_resp.json()["data"]["csrf_token"]},
            json={"code": "bad_role", "name": "未授权创建"},
        )
        assert forbidden_csrf.status_code == 403


async def test_audit_logs_filtering(client, admin_session):
    logs = await client.get(
        "/api/v1/admin/audit-logs",
        params={"action": "user.created", "result": "succeeded"},
    )
    assert logs.status_code == 200
    for item in logs.json()["data"]:
        assert item["action"] == "user.created"
        assert item["result"] == "succeeded"

    by_target = await client.get(
        "/api/v1/admin/audit-logs",
        params={"target_type": "user"},
    )
    assert by_target.status_code == 200
    assert len(by_target.json()["data"]) >= 1

    invalid_date = await client.get(
        "/api/v1/admin/audit-logs",
        params={"created_from": "not-a-date"},
    )
    assert invalid_date.status_code == 400
