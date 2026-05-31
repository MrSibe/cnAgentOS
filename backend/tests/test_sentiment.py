"""数智大屏与舆情分析集成测试 (Phase 8)."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from cnagentos.models.entities import (
    KnowledgeItem,
    ModelConfig,
    SentimentReport,
    SentimentTask,
    User,
    WatchSource,
)

ADMIN_PASSWORD = "Admin-password-123"


@pytest.fixture(autouse=True)
async def seed_test_data(app):
    """Seed minimal test data for dashboard stats and sentiment tests."""
    from cnagentos.security import encrypt

    async with app.state.sessionmaker() as session:
        # Get admin user ID
        admin = await session.scalar(select(User).where(User.username == "root"))
        admin_id = admin.id if admin else "root"

        # Create a model config (needed for sentiment task creation later)
        model = await session.scalar(select(ModelConfig).where(ModelConfig.name == "Test Sentiment Model"))
        if model is None:
            model = ModelConfig(
                id=str(uuid4()),
                name="Test Sentiment Model",
                provider_type="openai_compatible",
                model_name="gpt-4o-mini",
                base_url="https://api.openai.com/v1",
                credential_ciphertext=encrypt("sk-test-key"),
                credential_mask="sk-test",
                status="active",
                is_default=True,
                timeout_seconds=30,
            )
            session.add(model)

        # Seed watch sources
        for s in ["active", "active", "disabled"]:
            ws = WatchSource(
                id=str(uuid4()),
                name=f"Source-{uuid4().hex[:6]}",
                source_type="web",
                entry_url="https://example.com",
                allowed_hosts=["example.com"],
                status=s,
                created_by=admin_id,
            )
            session.add(ws)

        # Seed knowledge items
        for status in ["available", "available", "available", "excluded", "archived"]:
            ki = KnowledgeItem(
                id=str(uuid4()),
                source_id=str(uuid4()),
                title=f"Article about AI and data analysis - {uuid4().hex[:6]}",
                content="This is a test article content about artificial intelligence, data analysis, and machine learning. It discusses various topics in technology.",
                summary="A test article about AI technology and data analysis methods.",
                content_hash=uuid4().hex,
                status=status,
                collected_at=datetime(2026, 5, 30, 12, 0, 0, tzinfo=timezone.utc).replace(tzinfo=None),
            )
            session.add(ki)

        await session.commit()


class TestDashboardStats:

    async def test_requires_auth(self, client: AsyncClient):
        """未登录用户访问 dashboard 接口应当返回 401"""
        resp = await client.get("/api/v1/admin/dashboard/stats")
        assert resp.status_code == 401

    async def test_requires_permission(self, client: AsyncClient, app):
        """普通用户（default_user）无 sentiment.view 权限时返回 403"""
        # Register a default user
        resp = await client.post(
            "/api/v1/auth/register",
            json={"username": "testuser1", "password": "TestPass-12345", "display_name": "Test"},
        )
        assert resp.status_code == 201

        # Login as testuser
        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "testuser1", "password": "TestPass-12345"},
        )
        assert resp.status_code == 200

        resp = await client.get("/api/v1/admin/dashboard/stats")
        assert resp.status_code == 403

    async def test_stats_returns_aggregated_data(self, client: AsyncClient):
        """管理员可获取聚合统计数据"""
        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "root", "password": ADMIN_PASSWORD},
        )
        assert resp.status_code == 200
        csrf = resp.json()["data"]["csrf_token"]

        resp = await client.get("/api/v1/admin/dashboard/stats")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "knowledge_items" in data
        assert "watch_sources" in data
        assert "users" in data
        assert data["knowledge_items"].get("total", 0) >= 5
        assert "watch_sources" in data
        assert "users" in data

    async def test_trends_returns_date_series(self, client: AsyncClient):
        """趋势接口返回日期序列"""
        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "root", "password": ADMIN_PASSWORD},
        )
        assert resp.status_code == 200

        resp = await client.get("/api/v1/admin/dashboard/trends?days=7")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "knowledge_items" in data
        assert len(data["knowledge_items"]) == 7

    async def test_keywords_returns_word_frequencies(self, client: AsyncClient):
        """关键词接口返回词频列表"""
        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "root", "password": ADMIN_PASSWORD},
        )
        assert resp.status_code == 200

        resp = await client.get("/api/v1/admin/dashboard/keywords?limit=20")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert isinstance(data, list)
        if data:
            assert "word" in data[0]
            assert "count" in data[0]


class TestSentimentTasks:

    async def _login_admin(self, client: AsyncClient) -> tuple[str, str]:
        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "root", "password": ADMIN_PASSWORD},
        )
        assert resp.status_code == 200
        j = resp.json()["data"]
        return j["csrf_token"], j.get("session_id", "")

    async def test_create_task(self, client: AsyncClient):
        """管理员可创建舆情分析任务"""
        csrf, _ = await self._login_admin(client)

        resp = await client.post(
            "/api/v1/admin/sentiment/tasks",
            json={"name": "Test Analysis", "task_type": "keyword"},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["name"] == "Test Analysis"
        assert data["task_type"] == "keyword"
        assert data["status"] == "pending"

    async def test_create_task_without_csrf(self, client: AsyncClient):
        """创建任务没有 CSRF 返回 403"""
        await self._login_admin(client)

        resp = await client.post(
            "/api/v1/admin/sentiment/tasks",
            json={"name": "No CSRF", "task_type": "full"},
        )
        assert resp.status_code == 403

    async def test_list_tasks(self, client: AsyncClient):
        """可列出已创建的分析任务"""
        csrf, _ = await self._login_admin(client)

        # Create a couple tasks
        for name in ["Task A", "Task B"]:
            resp = await client.post(
                "/api/v1/admin/sentiment/tasks",
                json={"name": name, "task_type": "full"},
                headers={"X-CSRF-Token": csrf},
            )
            assert resp.status_code == 201

        resp = await client.get("/api/v1/admin/sentiment/tasks")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) >= 2

    async def test_get_task_detail(self, client: AsyncClient):
        """可获取任务详情"""
        csrf, _ = await self._login_admin(client)

        resp = await client.post(
            "/api/v1/admin/sentiment/tasks",
            json={"name": "Detail Test", "task_type": "full"},
            headers={"X-CSRF-Token": csrf},
        )
        task_id = resp.json()["data"]["id"]

        resp = await client.get(f"/api/v1/admin/sentiment/tasks/{task_id}")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["id"] == task_id
        assert data["name"] == "Detail Test"

    async def test_get_nonexistent_task(self, client: AsyncClient):
        """不存在的任务返回 404"""
        await self._login_admin(client)

        resp = await client.get(f"/api/v1/admin/sentiment/tasks/{uuid4()}")
        assert resp.status_code == 404

    async def test_run_task_no_default_model(self, client: AsyncClient, app):
        """无默认模型时运行任务返回 422"""
        # Remove default model flag
        async with app.state.sessionmaker() as session:
            models = (await session.scalars(select(ModelConfig))).all()
            for m in models:
                m.is_default = False
            await session.commit()

        csrf, _ = await self._login_admin(client)

        resp = await client.post(
            "/api/v1/admin/sentiment/tasks",
            json={"name": "Run No Model", "task_type": "full"},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 201
        task_id = resp.json()["data"]["id"]

        resp = await client.post(
            f"/api/v1/admin/sentiment/tasks/{task_id}/run",
            headers={"X-CSRF-Token": csrf},
        )
        # Should fail with 422 MODEL_UNAVAILABLE
        assert resp.status_code == 422

    async def test_task_reports_empty(self, client: AsyncClient):
        """尚未分析的 task 报告列表为空"""
        csrf, _ = await self._login_admin(client)

        resp = await client.post(
            "/api/v1/admin/sentiment/tasks",
            json={"name": "Empty Reports", "task_type": "full"},
            headers={"X-CSRF-Token": csrf},
        )
        task_id = resp.json()["data"]["id"]

        resp = await client.get(f"/api/v1/admin/sentiment/tasks/{task_id}/reports")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data == []

    async def test_get_nonexistent_report(self, client: AsyncClient):
        """不存在的报告返回 404"""
        await self._login_admin(client)

        resp = await client.get(f"/api/v1/admin/sentiment/reports/{uuid4()}")
        assert resp.status_code == 404
