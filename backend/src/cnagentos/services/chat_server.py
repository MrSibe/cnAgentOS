"""Chat Server management service — CRUD, health check, auto-selection."""

import time
from uuid import uuid4

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from cnagentos.api import ApiError
from cnagentos.models.entities import ChatServer, User, utc_now
from cnagentos.security import decrypt, encrypt, generate_mask


class ChatServerService:
    """Manage chat server configurations and health checks."""

    def __init__(
        self, session: AsyncSession, actor: User, ip_address: str | None = None,
    ) -> None:
        self.session = session
        self.actor = actor
        self.actor_id = actor.id
        self.ip_address = ip_address

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def list_servers(self, page: int = 1, page_size: int = 20) -> tuple[list[dict], int]:
        total = (await self.session.scalar(select(func.count(ChatServer.id)))) or 0
        rows = (
            (
                await self.session.scalars(
                    select(ChatServer)
                    .options(selectinload(ChatServer.creator))
                    .order_by(ChatServer.priority.asc(), ChatServer.created_at.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            )
            .all()
        )
        return [self._to_dict(s) for s in rows], total

    async def create_server(self, payload) -> dict:
        auth_ciphertext = None
        auth_mask = None
        if payload.auth_token:
            try:
                auth_ciphertext = encrypt(payload.auth_token)
            except RuntimeError:
                raise ApiError(500, "INTERNAL_ERROR", "加密模块未初始化")
            auth_mask = generate_mask(payload.auth_token)

        server = ChatServer(
            id=str(uuid4()),
            name=payload.name,
            base_url=payload.base_url,
            health_check_url=payload.health_check_url,
            auth_ciphertext=auth_ciphertext,
            auth_mask=auth_mask,
            priority=payload.priority,
            status="disabled",
            created_by=self.actor_id,
        )
        self.session.add(server)
        await self.session.commit()
        await self.session.refresh(server)
        return self._to_dict(server)

    async def get_server(self, server_id: str) -> dict:
        server = await self.session.get(
            ChatServer, server_id,
            options=[selectinload(ChatServer.creator)],
        )
        if server is None:
            raise ApiError(404, "NOT_FOUND", "服务器不存在")
        return self._to_dict(server)

    async def update_server(self, server_id: str, payload) -> dict:
        server = await self.session.get(ChatServer, server_id)
        if server is None:
            raise ApiError(404, "NOT_FOUND", "服务器不存在")

        update_data = payload.model_dump(exclude_unset=True)
        if "name" in update_data:
            server.name = update_data["name"]
        if "base_url" in update_data:
            server.base_url = update_data["base_url"]
        if "health_check_url" in update_data:
            server.health_check_url = update_data["health_check_url"]
        if "auth_token" in update_data and update_data["auth_token"]:
            try:
                server.auth_ciphertext = encrypt(update_data["auth_token"])
            except RuntimeError:
                raise ApiError(500, "INTERNAL_ERROR", "加密模块未初始化")
            server.auth_mask = generate_mask(update_data["auth_token"])
        if "priority" in update_data:
            server.priority = update_data["priority"]

        server.updated_at = utc_now()
        await self.session.commit()
        await self.session.refresh(server)
        return self._to_dict(server)

    async def update_server_status(self, server_id: str, status: str) -> dict:
        if status not in ("active", "disabled"):
            raise ApiError(400, "VALIDATION_ERROR", "状态必须是 active 或 disabled")
        server = await self.session.get(ChatServer, server_id)
        if server is None:
            raise ApiError(404, "NOT_FOUND", "服务器不存在")
        server.status = status
        server.updated_at = utc_now()
        await self.session.commit()
        await self.session.refresh(server)
        return self._to_dict(server)

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    async def health_check(self, server_id: str) -> dict:
        server = await self.session.get(ChatServer, server_id)
        if server is None:
            raise ApiError(404, "NOT_FOUND", "服务器不存在")

        url = server.health_check_url or f"{server.base_url.rstrip('/')}/health"
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url)
                elapsed = int((time.monotonic() - start) * 1000)
                if resp.status_code == 200:
                    server.last_health_check_result = "passed"
                    server.last_health_check_at = utc_now()
                    server.status = "active"
                else:
                    server.last_health_check_result = "failed"
                    server.last_health_check_at = utc_now()
                    server.status = "unhealthy"
                    # Infer from response
                server.updated_at = utc_now()
                await self.session.commit()
                return {
                    "server_id": server.id,
                    "status": server.status,
                    "result": server.last_health_check_result,
                    "latency_ms": elapsed,
                    "checked_at": server.last_health_check_at.isoformat() if server.last_health_check_at else None,
                }
        except Exception as e:
            elapsed = int((time.monotonic() - start) * 1000)
            server.last_health_check_result = "failed"
            server.last_health_check_at = utc_now()
            server.status = "unhealthy"
            server.updated_at = utc_now()
            await self.session.commit()
            return {
                "server_id": server.id,
                "status": server.status,
                "result": "failed",
                "error": str(e)[:200],
                "latency_ms": elapsed,
                "checked_at": server.last_health_check_at.isoformat() if server.last_health_check_at else None,
            }

    async def get_active_server(self) -> dict | None:
        """Auto-select the best active server (highest priority + health)."""
        servers = (
            (
                await self.session.scalars(
                    select(ChatServer)
                    .where(ChatServer.status == "active")
                    .order_by(ChatServer.priority.asc())
                )
            )
            .all()
        )
        if not servers:
            return None
        return self._to_dict(servers[0])

    async def switch_server(self, server_id: str) -> dict:
        """Manually switch to a specific server by deactivating others."""
        target = await self.session.get(ChatServer, server_id)
        if target is None:
            raise ApiError(404, "NOT_FOUND", "服务器不存在")

        # Deactivate all other active servers
        others = (
            (
                await self.session.scalars(
                    select(ChatServer).where(
                        ChatServer.id != server_id,
                        ChatServer.status == "active",
                    )
                )
            )
            .all()
        )
        for s in others:
            s.status = "disabled"
            s.updated_at = utc_now()

        target.status = "active"
        target.updated_at = utc_now()
        await self.session.commit()
        await self.session.refresh(target)
        return self._to_dict(target)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _to_dict(self, server: ChatServer) -> dict:
        return {
            "id": server.id,
            "name": server.name,
            "base_url": server.base_url,
            "health_check_url": server.health_check_url,
            "auth_mask": server.auth_mask,
            "priority": server.priority,
            "status": server.status,
            "last_health_check_at": server.last_health_check_at.isoformat() if server.last_health_check_at else None,
            "last_health_check_result": server.last_health_check_result,
            "created_by": server.creator.username if server.creator else None,
            "created_at": server.created_at.isoformat() if server.created_at else None,
            "updated_at": server.updated_at.isoformat() if server.updated_at else None,
        }
