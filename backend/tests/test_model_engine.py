import json

import httpx
import pytest
from openai import APIConnectionError, APIStatusError, APITimeoutError

from cnagentos.services.model_provider import ModelProviderResponse, ModelProviderUsage


async def create_active_model(client, admin_session, name="SDK 测试模型"):
    created = await client.post(
        "/api/v1/admin/models",
        headers={"X-CSRF-Token": admin_session},
        json={
            "name": name,
            "provider_type": "openai_compatible",
            "model_name": "gpt-4o-mini",
            "base_url": "https://api.example.com/v1",
            "api_key": "test-sdk-key-123456789",
            "timeout_seconds": 30,
        },
    )
    assert created.status_code == 201
    model_id = created.json()["data"]["id"]
    activated = await client.patch(
        f"/api/v1/admin/models/{model_id}/status",
        headers={"X-CSRF-Token": admin_session},
        json={"status": "active"},
    )
    assert activated.status_code == 200
    return model_id


class FakeProviderClient:
    response = ModelProviderResponse(
        reply="连接正常",
        usage=ModelProviderUsage(prompt_tokens=10, completion_tokens=4, total_tokens=14),
    )
    error = None
    stream_chunks = [
        {"choices": [{"delta": {"content": "连接"}}]},
        {"choices": [{"delta": {"content": "正常"}}]},
    ]
    stream_error = None
    init_kwargs = []

    def __init__(self, api_key, base_url, timeout_seconds):
        self.__class__.init_kwargs.append(
            {
                "api_key": api_key,
                "base_url": base_url,
                "timeout_seconds": timeout_seconds,
            }
        )

    async def complete_chat(self, model_name, message):
        if self.error:
            raise self.error
        return self.response

    async def stream_chat(self, model_name, message):
        if self.stream_error:
            raise self.stream_error
        for chunk in self.stream_chunks:
            yield chunk


def reset_fake_provider():
    FakeProviderClient.response = ModelProviderResponse(
        reply="连接正常",
        usage=ModelProviderUsage(prompt_tokens=10, completion_tokens=4, total_tokens=14),
    )
    FakeProviderClient.error = None
    FakeProviderClient.stream_chunks = [
        {"choices": [{"delta": {"content": "连接"}}]},
        {"choices": [{"delta": {"content": "正常"}}]},
    ]
    FakeProviderClient.stream_error = None
    FakeProviderClient.init_kwargs = []


def openai_request():
    return httpx.Request("POST", "https://api.example.com/v1/chat/completions")


async def test_model_config_crud(client, admin_session):
    created = await client.post(
        "/api/v1/admin/models",
        headers={"X-CSRF-Token": admin_session},
        json={
            "name": "测试模型",
            "provider_type": "openai_compatible",
            "model_name": "gpt-4o-mini",
            "base_url": "https://api.openai.com/v1",
            "api_key": "test-key-for-testing-123456789",
            "timeout_seconds": 30,
            "description": "用于测试的模型",
        },
    )
    assert created.status_code == 201
    data = created.json()["data"]
    model_id = data["id"]
    assert data["name"] == "测试模型"
    assert data["credential_mask"] == "****6789"
    assert data["status"] == "disabled"
    assert data["is_default"] is False
    body_str = json.dumps(created.json())
    assert "test-api-key" not in body_str
    assert "credential_ciphertext" not in body_str

    single = await client.get(f"/api/v1/admin/models/{model_id}")
    assert single.status_code == 200
    assert single.json()["data"]["id"] == model_id

    updated = await client.patch(
        f"/api/v1/admin/models/{model_id}",
        headers={"X-CSRF-Token": admin_session},
        json={"name": "测试模型改", "api_key": "test-new-key-abcdefghijk"},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["name"] == "测试模型改"
    assert updated.json()["data"]["credential_mask"] == "****hijk"

    no_key_update = await client.patch(
        f"/api/v1/admin/models/{model_id}",
        headers={"X-CSRF-Token": admin_session},
        json={"timeout_seconds": 45},
    )
    assert no_key_update.status_code == 200
    assert no_key_update.json()["data"]["timeout_seconds"] == 45
    assert no_key_update.json()["data"]["credential_mask"] == "****hijk"


async def test_model_list_pagination_and_filters(client, admin_session):
    await client.post(
        "/api/v1/admin/models",
        headers={"X-CSRF-Token": admin_session},
        json={
            "name": "模型甲",
            "model_name": "model-a",
            "base_url": "https://api.example.com/v1",
            "api_key": "test-model-a-key-123456",
        },
    )
    await client.post(
        "/api/v1/admin/models",
        headers={"X-CSRF-Token": admin_session},
        json={
            "name": "模型乙",
            "model_name": "model-b",
            "base_url": "https://api.example.com/v1",
            "api_key": "test-model-b-key-789012",
        },
    )

    models = await client.get("/api/v1/admin/models")
    assert models.status_code == 200
    assert models.json()["meta"]["total"] >= 2

    paged = await client.get("/api/v1/admin/models", params={"page": 1, "page_size": 1})
    assert paged.status_code == 200
    assert len(paged.json()["data"]) == 1

    search = await client.get("/api/v1/admin/models", params={"q": "模型甲"})
    assert search.status_code == 200
    assert any(m["name"] == "模型甲" for m in search.json()["data"])

    by_status = await client.get("/api/v1/admin/models", params={"status": "disabled"})
    assert by_status.status_code == 200

    invalid_status = await client.get("/api/v1/admin/models", params={"status": "deleted"})
    assert invalid_status.status_code == 400


async def test_model_status_activation_and_default(client, admin_session):
    created = await client.post(
        "/api/v1/admin/models",
        headers={"X-CSRF-Token": admin_session},
        json={
            "name": "默认测试模型",
            "model_name": "test-model",
            "base_url": "https://api.example.com/v1",
            "api_key": "test-default-test-key-123456",
        },
    )
    model_id = created.json()["data"]["id"]

    activate = await client.patch(
        f"/api/v1/admin/models/{model_id}/status",
        headers={"X-CSRF-Token": admin_session},
        json={"status": "active"},
    )
    assert activate.status_code == 200
    assert activate.json()["data"]["status"] == "active"

    set_default = await client.put(
        f"/api/v1/admin/models/{model_id}/default",
        headers={"X-CSRF-Token": admin_session},
    )
    assert set_default.status_code == 200
    assert set_default.json()["data"]["is_default"] is True

    disable = await client.patch(
        f"/api/v1/admin/models/{model_id}/status",
        headers={"X-CSRF-Token": admin_session},
        json={"status": "disabled"},
    )
    assert disable.status_code == 409
    assert disable.json()["error"]["code"] == "INVALID_STATE"


async def test_model_requires_https(client, admin_session):
    resp = await client.post(
        "/api/v1/admin/models",
        headers={"X-CSRF-Token": admin_session},
        json={
            "name": "不安全模型",
            "model_name": "model",
            "base_url": "http://insecure.example.com/v1",
            "api_key": "test-insecure-key-123",
        },
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_model_not_found(client, admin_session):
    resp = await client.get("/api/v1/admin/models/nonexistent-id")
    assert resp.status_code == 404

    resp = await client.patch(
        "/api/v1/admin/models/nonexistent-id",
        headers={"X-CSRF-Token": admin_session},
        json={"name": "改名"},
    )
    assert resp.status_code == 404


async def test_model_permission_enforcement(client, app, admin_session):
    # 获取 models.view 权限
    permissions = await client.get("/api/v1/admin/permissions")
    permissions_data = permissions.json()["data"]
    models_view_perm = next(p for p in permissions_data if p["code"] == "models.view")
    models_manage_perm = next(p for p in permissions_data if p["code"] == "models.manage")

    # 创建只有 models.view 权限的角色
    viewer_role_resp = await client.post(
        "/api/v1/admin/roles",
        headers={"X-CSRF-Token": admin_session},
        json={
            "code": "model_viewer_role",
            "name": "模型查看者",
            "permission_ids": [models_view_perm["id"]],
        },
    )
    assert viewer_role_resp.status_code == 201
    viewer_role_id = viewer_role_resp.json()["data"]["id"]

    # 创建只有 models.view 权限的用户
    viewer_resp = await client.post(
        "/api/v1/admin/users",
        headers={"X-CSRF-Token": admin_session},
        json={
            "username": "model_viewer",
            "display_name": "模型观察者",
            "password": "Viewer-password-123",
            "role_ids": [viewer_role_id],
        },
    )
    assert viewer_resp.status_code == 201

    from httpx import ASGITransport, AsyncClient
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as viewer_client:
        login_resp = await viewer_client.post(
            "/api/v1/auth/login",
            json={"username": "model_viewer", "password": "Viewer-password-123"},
        )
        assert login_resp.status_code == 200
        viewer_csrf = login_resp.json()["data"]["csrf_token"]

        # 有 models.view 权限，应该能查看
        view_ok = await viewer_client.get("/api/v1/admin/models")
        assert view_ok.status_code == 200

        # 没有 models.manage 权限，应该被拒绝创建
        create_forbidden = await viewer_client.post(
            "/api/v1/admin/models",
            headers={"X-CSRF-Token": viewer_csrf},
            json={
                "name": "非法创建",
                "model_name": "test",
                "base_url": "https://api.example.com/v1",
                "api_key": "test-key-123",
            },
        )
        assert create_forbidden.status_code == 403
        assert create_forbidden.json()["error"]["code"] == "PERMISSION_DENIED"

    # 测试无角色用户（应返回 403）
    no_role_resp = await client.post(
        "/api/v1/admin/users",
        headers={"X-CSRF-Token": admin_session},
        json={
            "username": "no_role_user",
            "display_name": "无角色用户",
            "password": "Norole-password-123",
            "role_ids": [],
        },
    )
    assert no_role_resp.status_code == 201

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as no_role_client:
        login_no_role = await no_role_client.post(
            "/api/v1/auth/login",
            json={"username": "no_role_user", "password": "Norole-password-123"},
        )
        assert login_no_role.status_code == 200

        view_forbidden = await no_role_client.get("/api/v1/admin/models")
        assert view_forbidden.status_code == 403
        assert view_forbidden.json()["error"]["code"] == "PERMISSION_DENIED"


async def test_model_call_logs_listing(client, admin_session):
    logs = await client.get("/api/v1/admin/model-calls")
    assert logs.status_code == 200
    assert "data" in logs.json()

    by_purpose = await client.get("/api/v1/admin/model-calls", params={"purpose": "connection_test"})
    assert by_purpose.status_code == 200

    by_status = await client.get("/api/v1/admin/model-calls", params={"status": "failed"})
    assert by_status.status_code == 200

    invalid_purpose = await client.get("/api/v1/admin/model-calls", params={"purpose": "invalid"})
    assert invalid_purpose.status_code == 400


async def test_model_call_summary(client, admin_session):
    summary = await client.get("/api/v1/admin/model-calls/summary")
    assert summary.status_code == 200
    data = summary.json()["data"]
    assert "total_calls" in data
    assert "succeeded_calls" in data
    assert "failed_calls" in data


async def test_model_credential_mask_generation(client, admin_session):
    short_key = await client.post(
        "/api/v1/admin/models",
        headers={"X-CSRF-Token": admin_session},
        json={
            "name": "短密钥模型",
            "model_name": "model",
            "base_url": "https://api.example.com/v1",
            "api_key": "abc",
        },
    )
    assert short_key.status_code == 201
    assert short_key.json()["data"]["credential_mask"] == "********"


async def test_connection_test_uses_openai_provider(monkeypatch, client, admin_session):
    reset_fake_provider()
    monkeypatch.setattr("cnagentos.services.model_engine.ModelProviderClient", FakeProviderClient)
    model_id = await create_active_model(client, admin_session)

    response = await client.post(
        f"/api/v1/admin/models/{model_id}/connection-tests",
        headers={"X-CSRF-Token": admin_session},
        json={"message": "请回复连接正常", "stream": False},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["reply"] == "连接正常"
    assert data["usage"] == {
        "prompt_tokens": 10,
        "completion_tokens": 4,
        "total_tokens": 14,
    }
    assert FakeProviderClient.init_kwargs[-1]["base_url"] == "https://api.example.com/v1"
    logs = await client.get("/api/v1/admin/model-calls", params={"model_id": model_id})
    log = logs.json()["data"][0]
    assert log["status"] == "succeeded"
    assert log["streamed"] is False
    assert log["total_tokens"] == 14


@pytest.mark.parametrize(
    ("error", "status_code", "api_code", "log_code"),
    [
        (APITimeoutError(request=openai_request()), 504, "TIMEOUT", "TIMEOUT"),
        (
            APIConnectionError(request=openai_request()),
            502,
            "CONNECTION_ERROR",
            "CONNECTION_ERROR",
        ),
        (
            APIStatusError(
                "upstream failed",
                response=httpx.Response(500, request=openai_request()),
                body=None,
            ),
            502,
            "UPSTREAM_ERROR",
            "UPSTREAM_ERROR",
        ),
    ],
)
async def test_connection_test_maps_openai_errors(
    monkeypatch, client, admin_session, error, status_code, api_code, log_code
):
    reset_fake_provider()
    FakeProviderClient.error = error
    monkeypatch.setattr("cnagentos.services.model_engine.ModelProviderClient", FakeProviderClient)
    model_id = await create_active_model(client, admin_session, name=f"错误模型 {log_code}")

    response = await client.post(
        f"/api/v1/admin/models/{model_id}/connection-tests",
        headers={"X-CSRF-Token": admin_session},
        json={"message": "请回复连接正常", "stream": False},
    )

    assert response.status_code == status_code
    assert response.json()["error"]["code"] == api_code
    logs = await client.get("/api/v1/admin/model-calls", params={"model_id": model_id})
    log = logs.json()["data"][0]
    assert log["status"] == "failed"
    assert log["error_code"] == log_code


async def test_stream_connection_test_uses_openai_provider(monkeypatch, client, admin_session):
    reset_fake_provider()
    monkeypatch.setattr("cnagentos.services.model_engine.ModelProviderClient", FakeProviderClient)
    model_id = await create_active_model(client, admin_session, name="流式 SDK 测试模型")

    async with client.stream(
        "POST",
        f"/api/v1/admin/models/{model_id}/connection-tests/stream",
        headers={"X-CSRF-Token": admin_session},
        json={"message": "请回复连接正常"},
    ) as response:
        body = await response.aread()

    text = body.decode()
    assert response.status_code == 200
    assert '"content": "连接"' in text
    assert '"content": "正常"' in text
    assert '"event": "completed"' in text
    assert "data: [DONE]" in text
    logs = await client.get("/api/v1/admin/model-calls", params={"model_id": model_id})
    log = logs.json()["data"][0]
    assert log["status"] == "succeeded"
    assert log["streamed"] is True


async def test_stream_connection_test_marks_openai_error(
    monkeypatch, client, admin_session
):
    reset_fake_provider()
    FakeProviderClient.stream_error = APIStatusError(
        "upstream failed",
        response=httpx.Response(503, request=openai_request()),
        body=None,
    )
    monkeypatch.setattr("cnagentos.services.model_engine.ModelProviderClient", FakeProviderClient)
    model_id = await create_active_model(client, admin_session, name="流式错误模型")

    async with client.stream(
        "POST",
        f"/api/v1/admin/models/{model_id}/connection-tests/stream",
        headers={"X-CSRF-Token": admin_session},
        json={"message": "请回复连接正常"},
    ) as response:
        body = await response.aread()

    text = body.decode()
    assert response.status_code == 200
    assert "event: error" in text
    assert '"event": "error"' in text
    assert '"code": "HTTP_503"' in text
    assert "data: [DONE]" in text
    logs = await client.get("/api/v1/admin/model-calls", params={"model_id": model_id})
    log = logs.json()["data"][0]
    assert log["status"] == "failed"
    assert log["error_code"] == "HTTP_503"


async def test_stream_connection_test_marks_connection_error(
    monkeypatch, client, admin_session
):
    reset_fake_provider()
    FakeProviderClient.stream_error = APIConnectionError(request=openai_request())
    monkeypatch.setattr("cnagentos.services.model_engine.ModelProviderClient", FakeProviderClient)
    model_id = await create_active_model(client, admin_session, name="流式连接错误模型")

    async with client.stream(
        "POST",
        f"/api/v1/admin/models/{model_id}/connection-tests/stream",
        headers={"X-CSRF-Token": admin_session},
        json={"message": "请回复连接正常"},
    ) as response:
        body = await response.aread()

    text = body.decode()
    assert response.status_code == 200
    assert "event: error" in text
    assert '"code": "CONNECTION_ERROR"' in text
    assert "data: [DONE]" in text
    logs = await client.get("/api/v1/admin/model-calls", params={"model_id": model_id})
    log = logs.json()["data"][0]
    assert log["status"] == "failed"
    assert log["error_code"] == "CONNECTION_ERROR"
