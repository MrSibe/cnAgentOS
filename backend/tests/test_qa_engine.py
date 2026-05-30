"""智能问数集成测试"""

import json
from uuid import uuid4

import httpx
from httpx import AsyncClient
import pytest
from sqlalchemy import func, select

from cnagentos.models.entities import AuditLog, KnowledgeItem, ModelCallLog
from cnagentos.services.model_provider import ModelProviderResponse, ModelProviderUsage

ADMIN_PASSWORD = "Admin-password-123"


class FakeQAProviderClient:
    """Mock provider for QA streaming tests"""
    
    response = ModelProviderResponse(
        reply="根据采集到的信息，这是关于人工智能的最新发展情况。",
        usage=ModelProviderUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
    )
    error = None
    stream_chunks = [
        {"choices": [{"delta": {"content": "根据"}}]},
        {"choices": [{"delta": {"content": "采集"}}]},
        {"choices": [{"delta": {"content": "到的"}}]},
        {"choices": [{"delta": {"content": "信息"}}]},
        {"choices": [{"delta": {"content": "，"}}]},
        {"choices": [{"delta": {"content": "这是"}}]},
        {"choices": [{"delta": {"content": "关于"}}]},
        {"choices": [{"delta": {"content": "人工"}}]},
        {"choices": [{"delta": {"content": "智能"}}]},
        {"choices": [{"delta": {"content": "的"}}]},
        {"choices": [{"delta": {"content": "最新"}}]},
        {"choices": [{"delta": {"content": "发展"}}]},
        {"choices": [{"delta": {"content": "情况"}}]},
        {"choices": [{"delta": {"content": "。"}}]},
    ]
    stream_error = None
    init_kwargs = []
    call_args = []
    
    def __init__(self, api_key, base_url, timeout_seconds):
        self.__class__.init_kwargs.append({
            "api_key": api_key,
            "base_url": base_url,
            "timeout_seconds": timeout_seconds,
        })
        self._api_key = api_key
        self._base_url = base_url
        self._timeout = timeout_seconds
    
    async def complete_chat(self, model_name, message):
        self.__class__.call_args.append({"method": "complete_chat", "model": model_name, "message": message})
        if self.error:
            raise self.error
        return self.response
    
    async def stream_chat(self, model_name, message):
        self.__class__.call_args.append({"method": "stream_chat", "model": model_name, "message": message})
        if self.stream_error:
            raise self.stream_error
        for chunk in self.stream_chunks:
            yield chunk


def reset_fake_qa_provider():
    FakeQAProviderClient.init_kwargs = []
    FakeQAProviderClient.call_args = []
    FakeQAProviderClient.error = None
    FakeQAProviderClient.stream_error = None
    FakeQAProviderClient.response = ModelProviderResponse(
        reply="根据采集到的信息，这是关于人工智能的最新发展情况。",
        usage=ModelProviderUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
    )
    FakeQAProviderClient.stream_chunks = [
        {"choices": [{"delta": {"content": "根据"}}]},
        {"choices": [{"delta": {"content": "采集"}}]},
        {"choices": [{"delta": {"content": "到的"}}]},
        {"choices": [{"delta": {"content": "信息"}}]},
        {"choices": [{"delta": {"content": "，"}}]},
        {"choices": [{"delta": {"content": "这是"}}]},
        {"choices": [{"delta": {"content": "关于"}}]},
        {"choices": [{"delta": {"content": "人工"}}]},
        {"choices": [{"delta": {"content": "智能"}}]},
        {"choices": [{"delta": {"content": "的"}}]},
        {"choices": [{"delta": {"content": "最新"}}]},
        {"choices": [{"delta": {"content": "发展"}}]},
        {"choices": [{"delta": {"content": "情况"}}]},
        {"choices": [{"delta": {"content": "。"}}]},
    ]


async def create_qa_user_with_permission(client, admin_session):
    """创建具有 qa.use 权限的普通用户"""
    permissions = await client.get("/api/v1/admin/permissions")
    if permissions.status_code != 200:
        raise RuntimeError(f"Failed to get permissions: {permissions.text}")
    permissions_data = permissions.json()["data"]
    qa_use_perm = next(p for p in permissions_data if p["code"] == "qa.use")
    
    role_resp = await client.post(
        "/api/v1/admin/roles",
        headers={"X-CSRF-Token": admin_session},
        json={
            "code": f"qa_user_role_{uuid4().hex[:8]}",
            "name": "问数用户",
            "permission_ids": [qa_use_perm["id"]],
        },
    )
    if role_resp.status_code != 201:
        raise RuntimeError(f"Failed to create role: {role_resp.text}")
    role_id = role_resp.json()["data"]["id"]
    
    user_resp = await client.post(
        "/api/v1/admin/users",
        headers={"X-CSRF-Token": admin_session},
        json={
            "username": f"qa_user_{uuid4().hex[:8]}",
            "display_name": "问数测试用户",
            "password": "QA-User-password-123",
            "role_ids": [role_id],
        },
    )
    if user_resp.status_code != 201:
        raise RuntimeError(f"Failed to create user: {user_resp.text}")
    # 直接使用创建响应中返回的数据，不需要额外调用 GET 接口
    return user_resp.json()["data"]["id"], user_resp.json()["data"]["username"]


async def create_qa_user_with_model_view(client, admin_session):
    """创建具有 qa.use 和 models.view 权限的测试用户"""
    permissions = await client.get("/api/v1/admin/permissions")
    if permissions.status_code != 200:
        raise RuntimeError(f"Failed to get permissions: {permissions.text}")
    permissions_data = permissions.json()["data"]
    qa_use_perm = next(p for p in permissions_data if p["code"] == "qa.use")
    models_view_perm = next(p for p in permissions_data if p["code"] == "models.view")
    
    role_resp = await client.post(
        "/api/v1/admin/roles",
        headers={"X-CSRF-Token": admin_session},
        json={
            "code": f"qa_model_role_{uuid4().hex[:8]}",
            "name": "问数+模型查看",
            "permission_ids": [qa_use_perm["id"], models_view_perm["id"]],
        },
    )
    if role_resp.status_code != 201:
        raise RuntimeError(f"Failed to create role: {role_resp.text}")
    role_id = role_resp.json()["data"]["id"]
    
    user_resp = await client.post(
        "/api/v1/admin/users",
        headers={"X-CSRF-Token": admin_session},
        json={
            "username": f"qa_model_user_{uuid4().hex[:8]}",
            "display_name": "问数模型测试用户",
            "password": "QA-Model-password-123",
            "role_ids": [role_id],
        },
    )
    if user_resp.status_code != 201:
        raise RuntimeError(f"Failed to create user: {user_resp.text}")
    return user_resp.json()["data"]["id"], user_resp.json()["data"]["username"]


async def login_qa_user(client, username, password):
    """登录问数用户并返回 CSRF token"""
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert login_resp.status_code == 200
    return login_resp.json()["data"]["csrf_token"]


async def create_active_model_for_qa(client, admin_session):
    """创建并启用模型用于 QA 测试"""
    created = await client.post(
        "/api/v1/admin/models",
        headers={"X-CSRF-Token": admin_session},
        json={
            "name": "QA 测试模型",
            "provider_type": "openai_compatible",
            "model_name": "gpt-4o-mini",
            "base_url": "https://api.example.com/v1",
            "api_key": "test-qa-key-123456789",
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
    
    # 清除之前的默认模型，避免冲突
    current_models = await client.get("/api/v1/admin/models")
    if current_models.status_code == 200:
        for m in current_models.json().get("data", []):
            if m.get("is_default") and m["id"] != model_id:
                # 先停用旧默认模型
                await client.patch(
                    f"/api/v1/admin/models/{m['id']}/status",
                    headers={"X-CSRF-Token": admin_session},
                    json={"status": "disabled"},
                )
    
    set_default = await client.put(
        f"/api/v1/admin/models/{model_id}/default",
        headers={"X-CSRF-Token": admin_session},
    )
    assert set_default.status_code == 200
    
    return model_id


async def create_available_knowledge(app, *, title="人工智能发展", content=None):
    """创建可用于问数检索的知识内容"""
    async with app.state.sessionmaker() as session:
        item = KnowledgeItem(
            id=str(uuid4()),
            title=title,
            content=content or "人工智能产业正在快速发展，模型应用和数据治理成为最新重点。",
            content_hash=uuid4().hex,
            status="available",
        )
        session.add(item)
        await session.commit()
        return item.id


def parse_completed_event(text: str) -> dict:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line == "event: completed" and index + 1 < len(lines):
            data_line = lines[index + 1]
            if data_line.startswith("data: "):
                return json.loads(data_line.removeprefix("data: "))
    raise AssertionError(f"completed event not found in SSE body: {text}")


async def audit_actions_for(app, target_id: str) -> list[str]:
    async with app.state.sessionmaker() as session:
        rows = (
            await session.scalars(
                select(AuditLog)
                .where(AuditLog.target_id == target_id)
                .order_by(AuditLog.created_at)
            )
        ).all()
        return [row.action for row in rows]


# =============================================================================
# 会话管理测试
# =============================================================================

async def test_qa_requires_permission(client, admin_session):
    """无 qa.use 权限的用户不能访问问数接口"""
    from httpx import ASGITransport, AsyncClient
    
    permissions = await client.get("/api/v1/admin/permissions")
    permissions_data = permissions.json()["data"]
    models_view_perm = next(p for p in permissions_data if p["code"] == "models.view")
    
    role_resp = await client.post(
        "/api/v1/admin/roles",
        headers={"X-CSRF-Token": admin_session},
        json={
            "code": f"no_qa_role_{uuid4().hex[:8]}",
            "name": "无问数权限",
            "permission_ids": [models_view_perm["id"]],
        },
    )
    assert role_resp.status_code == 201
    role_id = role_resp.json()["data"]["id"]
    
    user_resp = await client.post(
        "/api/v1/admin/users",
        headers={"X-CSRF-Token": admin_session},
        json={
            "username": f"no_qa_user_{uuid4().hex[:8]}",
            "display_name": "无问数权限用户",
            "password": "NoQA-password-123",
            "role_ids": [role_id],
        },
    )
    assert user_resp.status_code == 201
    
    async with AsyncClient(
        transport=ASGITransport(app=client._transport.app), base_url="http://testserver"
    ) as no_qa_client:
        login_resp = await no_qa_client.post(
            "/api/v1/auth/login",
            json={"username": user_resp.json()["data"]["username"], "password": "NoQA-password-123"},
        )
        assert login_resp.status_code == 200
        
        # 应该被拒绝访问
        forbidden = await no_qa_client.get("/api/v1/qa/sessions")
        assert forbidden.status_code == 403
        assert forbidden.json()["error"]["code"] == "PERMISSION_DENIED"


async def test_session_crud_operations(client, admin_session):
    """测试会话 CRUD 操作"""
    qa_user_id, username = await create_qa_user_with_permission(client, admin_session)
    qa_csrf = await login_qa_user(client, username, "QA-User-password-123")
    
    # 创建会话
    created = await client.post(
        "/api/v1/qa/sessions",
        headers={"X-CSRF-Token": qa_csrf},
        json={"title": "我的问数会话"},
    )
    assert created.status_code == 201
    session_data = created.json()["data"]
    session_id = session_data["id"]
    assert session_data["title"] == "我的问数会话"
    assert session_data["status"] == "active"
    
    # 获取会话
    single = await client.get(f"/api/v1/qa/sessions/{session_id}")
    assert single.status_code == 200
    assert single.json()["data"]["id"] == session_id
    
    # 列出会话
    sessions = await client.get("/api/v1/qa/sessions")
    assert sessions.status_code == 200
    assert any(s["id"] == session_id for s in sessions.json()["data"])
    
    # 更新会话
    updated = await client.patch(
        f"/api/v1/qa/sessions/{session_id}",
        headers={"X-CSRF-Token": qa_csrf},
        json={"title": "修改后的标题", "status": "archived"},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["title"] == "修改后的标题"
    assert updated.json()["data"]["status"] == "archived"


async def test_session_isolation_between_users(client, admin_session):
    """测试用户之间的会话隔离"""
    from httpx import ASGITransport
    
    # 用 admin 会话创建两个用户
    user1_id, user1_name = await create_qa_user_with_permission(client, admin_session)
    
    # 重新登录 admin 以便创建第二个用户
    admin_relogin_resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "root", "password": ADMIN_PASSWORD},
    )
    assert admin_relogin_resp.status_code == 200
    admin_csrf = admin_relogin_resp.json()["data"]["csrf_token"]
    
    user2_id, user2_name = await create_qa_user_with_permission(client, admin_csrf)
    
    # 用户1登录并创建会话
    user1_login = await client.post(
        "/api/v1/auth/login",
        json={"username": user1_name, "password": "QA-User-password-123"},
    )
    assert user1_login.status_code == 200
    user1_csrf = user1_login.json()["data"]["csrf_token"]
    
    user1_session = await client.post(
        "/api/v1/qa/sessions",
        headers={"X-CSRF-Token": user1_csrf},
        json={"title": "用户1的会话"},
    )
    assert user1_session.status_code == 201
    session_id = user1_session.json()["data"]["id"]
    
    # 用户2使用独立的客户端登录
    async with AsyncClient(
        transport=ASGITransport(app=client._transport.app), base_url="http://testserver"
    ) as user2_client:
        user2_login = await user2_client.post(
            "/api/v1/auth/login",
            json={"username": user2_name, "password": "QA-User-password-123"},
        )
        assert user2_login.status_code == 200
        user2_csrf = user2_login.json()["data"]["csrf_token"]
        
        # 用户2不能访问用户1的会话（返回404避免信息泄露）
        user2_get = await user2_client.get(f"/api/v1/qa/sessions/{session_id}")
        assert user2_get.status_code == 404
        assert user2_get.json()["error"]["code"] == "NOT_FOUND"
        
        user2_update = await user2_client.patch(
            f"/api/v1/qa/sessions/{session_id}",
            headers={"X-CSRF-Token": user2_csrf},
            json={"title": "尝试修改"},
        )
        assert user2_update.status_code == 404
        
        user2_messages = await user2_client.get(f"/api/v1/qa/sessions/{session_id}/messages")
        assert user2_messages.status_code == 404


async def test_session_not_found(client, admin_session):
    """测试会话不存在的情况"""
    qa_user_id, username = await create_qa_user_with_permission(client, admin_session)
    qa_csrf = await login_qa_user(client, username, "QA-User-password-123")
    
    not_found = await client.get(f"/api/v1/qa/sessions/nonexistent-id")
    assert not_found.status_code == 404
    
    updated = await client.patch(
        "/api/v1/qa/sessions/nonexistent-id",
        headers={"X-CSRF-Token": qa_csrf},
        json={"title": "修改"},
    )
    assert updated.status_code == 404


# =============================================================================
# 消息列表测试
# =============================================================================

async def test_messages_empty_for_new_session(client, admin_session):
    """新会话没有消息"""
    qa_user_id, username = await create_qa_user_with_permission(client, admin_session)
    qa_csrf = await login_qa_user(client, username, "QA-User-password-123")
    
    created = await client.post(
        "/api/v1/qa/sessions",
        headers={"X-CSRF-Token": qa_csrf},
        json={"title": "空会话"},
    )
    session_id = created.json()["data"]["id"]
    
    messages = await client.get(f"/api/v1/qa/sessions/{session_id}/messages")
    assert messages.status_code == 200
    assert messages.json()["data"] == []


# =============================================================================
# 模型不可用测试
# =============================================================================

async def test_ask_question_requires_default_model(client, admin_session):
    """没有默认模型时不能提问"""
    qa_user_id, username = await create_qa_user_with_permission(client, admin_session)
    qa_csrf = await login_qa_user(client, username, "QA-User-password-123")
    
    # 不创建任何模型
    created = await client.post(
        "/api/v1/qa/sessions",
        headers={"X-CSRF-Token": qa_csrf},
        json={"title": "测试会话"},
    )
    session_id = created.json()["data"]["id"]
    
    # 尝试提问应该失败
    ask = await client.post(
        f"/api/v1/qa/sessions/{session_id}/questions/stream",
        headers={"X-CSRF-Token": qa_csrf},
        json={"question": "测试问题"},
    )
    assert ask.status_code == 422
    assert ask.json()["error"]["code"] == "MODEL_UNAVAILABLE"


# =============================================================================
# 流式问答测试
# =============================================================================

async def test_streaming_qa_success(monkeypatch, app, client, admin_session):
    """测试成功的流式问答"""
    reset_fake_qa_provider()
    monkeypatch.setattr("cnagentos.services.qa_engine.ModelProviderClient", FakeQAProviderClient)
    await create_available_knowledge(app)
    
    model_id = await create_active_model_for_qa(client, admin_session)
    qa_user_id, username = await create_qa_user_with_model_view(client, admin_session)
    qa_csrf = await login_qa_user(client, username, "QA-Model-password-123")
    
    created = await client.post(
        "/api/v1/qa/sessions",
        headers={"X-CSRF-Token": qa_csrf},
        json={"title": "流式问答测试"},
    )
    session_id = created.json()["data"]["id"]
    
    async with client.stream(
        "POST",
        f"/api/v1/qa/sessions/{session_id}/questions/stream",
        headers={"X-CSRF-Token": qa_csrf},
        json={"question": "关于人工智能的最新发展是什么？"},
    ) as response:
        body = await response.aread()
    
    text = body.decode()
    
    # 验证 SSE 流式响应
    assert response.status_code == 200
    assert "event: completed" in text or any("content" in line for line in text.split("\n") if line.startswith("data:"))
    completed_payload = parse_completed_event(text)
    assert completed_payload["citations"]
    
    # 验证消息已保存
    messages = await client.get(f"/api/v1/qa/sessions/{session_id}/messages")
    assert messages.status_code == 200
    msg_data = messages.json()["data"]
    
    # 应该有用户消息和助手回答
    assert len(msg_data) >= 2
    answer_msg = next(m for m in msg_data if m["role"] == "assistant")
    assert answer_msg["citations"]

    citations = await client.get(f"/api/v1/qa/messages/{answer_msg['id']}/citations")
    assert citations.status_code == 200
    assert citations.json()["data"]
    actions = await audit_actions_for(app, answer_msg["id"])
    assert "qa.answer.completed" in actions
    assert "qa.citations.viewed" in actions
    
    # 验证模型调用日志
    logs = await client.get("/api/v1/admin/model-calls")
    assert logs.status_code == 200
    qa_logs = [l for l in logs.json()["data"] if l["purpose"] == "qa_answer"]
    assert len(qa_logs) >= 1


async def test_streaming_qa_error_handling(monkeypatch, app, client, admin_session):
    """测试流式问答错误处理 - 验证错误时数据库状态正确更新"""
    from openai import APIStatusError
    
    reset_fake_qa_provider()
    await create_available_knowledge(app, title="错误处理资料", content="测试错误处理需要可用依据。")
    FakeQAProviderClient.stream_error = APIStatusError(
        "upstream failed",
        response=httpx.Response(503, request=httpx.Request("POST", "https://api.example.com/v1/chat/completions")),
        body=None,
    )
    monkeypatch.setattr("cnagentos.services.qa_engine.ModelProviderClient", FakeQAProviderClient)
    
    model_id = await create_active_model_for_qa(client, admin_session)
    qa_user_id, username = await create_qa_user_with_permission(client, admin_session)
    qa_csrf = await login_qa_user(client, username, "QA-User-password-123")
    
    created = await client.post(
        "/api/v1/qa/sessions",
        headers={"X-CSRF-Token": qa_csrf},
        json={"title": "错误处理测试"},
    )
    session_id = created.json()["data"]["id"]
    
    async with client.stream(
        "POST",
        f"/api/v1/qa/sessions/{session_id}/questions/stream",
        headers={"X-CSRF-Token": qa_csrf},
        json={"question": "测试错误处理"},
    ) as response:
        body = await response.aread()
    
    text = body.decode()
    
    # 验证错误事件
    assert response.status_code == 200
    assert "event: error" in text
    assert "HTTP_503" in text or "upstream" in text.lower()
    
    # 验证数据库状态已更新为 failed（修复 _handle_stream_error 死代码问题）
    messages_resp = await client.get(f"/api/v1/qa/sessions/{session_id}/messages")
    messages_data = messages_resp.json()
    
    answer_msg = next(m for m in messages_data["data"] if m["role"] == "assistant")
    assert answer_msg["status"] == "failed", f"期望 status=failed，实际 {answer_msg['status']}"
    assert answer_msg["error_summary"] is not None, "错误摘要应该被记录"
    assert "模型" in answer_msg["error_summary"] or "upstream" in answer_msg["error_summary"].lower()
    actions = await audit_actions_for(app, answer_msg["id"])
    assert "qa.answer.failed" in actions


async def test_cannot_ask_in_archived_session(client, admin_session):
    """归档会话不能提问"""
    model_id = await create_active_model_for_qa(client, admin_session)
    qa_user_id, username = await create_qa_user_with_permission(client, admin_session)
    qa_csrf = await login_qa_user(client, username, "QA-User-password-123")
    
    created = await client.post(
        "/api/v1/qa/sessions",
        headers={"X-CSRF-Token": qa_csrf},
        json={"title": "归档会话测试"},
    )
    session_id = created.json()["data"]["id"]
    
    # 先归档会话
    await client.patch(
        f"/api/v1/qa/sessions/{session_id}",
        headers={"X-CSRF-Token": qa_csrf},
        json={"status": "archived"},
    )
    
    # 尝试提问应该失败
    ask = await client.post(
        f"/api/v1/qa/sessions/{session_id}/questions/stream",
        headers={"X-CSRF-Token": qa_csrf},
        json={"question": "测试"},
    )
    assert ask.status_code == 400
    assert ask.json()["error"]["code"] == "INVALID_STATE"


async def test_streaming_question_requires_csrf(client, admin_session):
    """流式提问也是变更型请求，必须校验 CSRF token"""
    model_id = await create_active_model_for_qa(client, admin_session)
    qa_user_id, username = await create_qa_user_with_permission(client, admin_session)
    qa_csrf = await login_qa_user(client, username, "QA-User-password-123")

    created = await client.post(
        "/api/v1/qa/sessions",
        headers={"X-CSRF-Token": qa_csrf},
        json={"title": "流式 CSRF 测试"},
    )
    session_id = created.json()["data"]["id"]

    ask = await client.post(
        f"/api/v1/qa/sessions/{session_id}/questions/stream",
        json={"question": "没有 CSRF 的流式请求"},
    )

    assert ask.status_code == 403
    assert ask.json()["error"]["code"] == "CSRF_INVALID"


async def test_no_evidence_answer_does_not_call_provider(monkeypatch, app, client, admin_session):
    """无可用依据时返回固定回答、空引用，且不调用模型 provider"""
    reset_fake_qa_provider()
    monkeypatch.setattr("cnagentos.services.qa_engine.ModelProviderClient", FakeQAProviderClient)

    model_id = await create_active_model_for_qa(client, admin_session)
    qa_user_id, username = await create_qa_user_with_permission(client, admin_session)
    qa_csrf = await login_qa_user(client, username, "QA-User-password-123")

    created = await client.post(
        "/api/v1/qa/sessions",
        headers={"X-CSRF-Token": qa_csrf},
        json={"title": "无依据测试"},
    )
    session_id = created.json()["data"]["id"]

    async with client.stream(
        "POST",
        f"/api/v1/qa/sessions/{session_id}/questions/stream",
        headers={"X-CSRF-Token": qa_csrf},
        json={"question": "一个没有任何可用依据的问题"},
    ) as response:
        body = await response.aread()

    text = body.decode()
    assert response.status_code == 200
    assert "未找到可用于回答该问题的系统依据" in text
    assert FakeQAProviderClient.call_args == []

    completed_payload = parse_completed_event(text)
    assert completed_payload["citations"] == []

    messages = await client.get(f"/api/v1/qa/sessions/{session_id}/messages")
    answer_msg = next(m for m in messages.json()["data"] if m["role"] == "assistant")
    assert answer_msg["status"] == "completed"
    assert answer_msg["citations"] == []

    citations = await client.get(f"/api/v1/qa/messages/{answer_msg['id']}/citations")
    assert citations.status_code == 200
    assert citations.json()["data"] == []
    actions = await audit_actions_for(app, answer_msg["id"])
    assert "qa.answer.completed" in actions
    assert "qa.citations.viewed" in actions
    async with app.state.sessionmaker() as session:
        qa_call_count = await session.scalar(
            select(func.count()).select_from(ModelCallLog).where(ModelCallLog.purpose == "qa_answer")
        )
    assert qa_call_count == 0


# =============================================================================
# 引用测试
# =============================================================================

async def test_get_citations_permission_check(client, admin_session):
    """测试获取引用的权限检查"""
    qa_user_id, username = await create_qa_user_with_permission(client, admin_session)
    qa_csrf = await login_qa_user(client, username, "QA-User-password-123")
    
    # 用户A创建会话
    created = await client.post(
        "/api/v1/qa/sessions",
        headers={"X-CSRF-Token": qa_csrf},
        json={"title": "测试会话"},
    )
    session_id = created.json()["data"]["id"]
    
    # 获取消息列表
    messages = await client.get(f"/api/v1/qa/sessions/{session_id}/messages")
    assert messages.status_code == 200
    
    # 如果有回答消息，尝试获取引用
    msg_data = messages.json()["data"]
    for msg in msg_data:
        if msg["role"] == "assistant" and msg.get("citations"):
            citations = await client.get(f"/api/v1/qa/messages/{msg['id']}/citations")
            assert citations.status_code == 200


# =============================================================================
# CSRF 保护测试
# =============================================================================

async def test_session_create_requires_csrf(client, admin_session):
    """创建会话需要 CSRF token"""
    qa_user_id, username = await create_qa_user_with_permission(client, admin_session)
    qa_csrf = await login_qa_user(client, username, "QA-User-password-123")
    
    # 没有 CSRF token 应该失败
    no_csrf = await client.post(
        "/api/v1/qa/sessions",
        json={"title": "无 CSRF 测试"},
    )
    assert no_csrf.status_code == 403


async def test_session_update_requires_csrf(client, admin_session):
    """更新会话需要 CSRF token"""
    qa_user_id, username = await create_qa_user_with_permission(client, admin_session)
    qa_csrf = await login_qa_user(client, username, "QA-User-password-123")
    
    created = await client.post(
        "/api/v1/qa/sessions",
        headers={"X-CSRF-Token": qa_csrf},
        json={"title": "CSRF 测试"},
    )
    session_id = created.json()["data"]["id"]
    
    # 没有 CSRF token 应该失败
    no_csrf = await client.patch(
        f"/api/v1/qa/sessions/{session_id}",
        json={"title": "无 CSRF 修改"},
    )
    assert no_csrf.status_code == 403


async def test_question_stream_requires_csrf(client, admin_session):
    """流式提问需要 CSRF token"""
    await create_active_model_for_qa(client, admin_session)
    _, username = await create_qa_user_with_permission(client, admin_session)
    qa_csrf = await login_qa_user(client, username, "QA-User-password-123")

    created = await client.post(
        "/api/v1/qa/sessions",
        headers={"X-CSRF-Token": qa_csrf},
        json={"title": "提问 CSRF 测试"},
    )
    session_id = created.json()["data"]["id"]

    no_csrf = await client.post(
        f"/api/v1/qa/sessions/{session_id}/questions/stream",
        json={"question": "没有 CSRF 的提问"},
    )
    assert no_csrf.status_code == 403
