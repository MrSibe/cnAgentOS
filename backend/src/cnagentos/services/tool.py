"""Tool registry and invocation management service for Phase 7."""

import time
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from cnagentos.api import ApiError
from cnagentos.models.entities import (
    EmployeeToolBinding,
    Tool,
    ToolInvocationLog,
    User,
    utc_now,
)
from cnagentos.security import InvalidToken, decrypt, encrypt, generate_mask


class ToolService:
    """Manage tool registration, rate limiting, and invocation logging."""

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

    async def list_tools(
        self, page: int = 1, page_size: int = 20, q: str | None = None,
        status: str | None = None,
    ) -> tuple[list[dict], int]:
        query = select(Tool)
        count_query = select(func.count(Tool.id))
        if q:
            pattern = f"%{q}%"
            query = query.where(Tool.name.ilike(pattern) | Tool.code.ilike(pattern))
            count_query = count_query.where(
                Tool.name.ilike(pattern) | Tool.code.ilike(pattern),
            )
        if status:
            query = query.where(Tool.status == status)
            count_query = count_query.where(Tool.status == status)

        total = (await self.session.scalar(count_query)) or 0
        rows = (
            (
                await self.session.scalars(
                    query.options(selectinload(Tool.creator))
                    .order_by(Tool.created_at.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            )
            .all()
        )
        return [self._to_dict(t) for t in rows], total

    async def create_tool(self, payload) -> dict:
        code = payload.code.strip()
        existing = await self.session.scalar(select(Tool).where(Tool.code == code))
        if existing:
            raise ApiError(409, "CONFLICT", f"工具代码已存在: {code}")

        config_ciphertext = None
        config_mask = None
        if payload.sensitive_config:
            try:
                config_ciphertext = encrypt(payload.sensitive_config)
            except RuntimeError:
                raise ApiError(500, "INTERNAL_ERROR", "加密模块未初始化")
            config_mask = generate_mask(payload.sensitive_config)

        tool = Tool(
            id=str(uuid4()),
            code=code,
            name=payload.name,
            description=payload.description,
            tool_type=payload.tool_type,
            config=payload.config,
            config_ciphertext=config_ciphertext,
            config_mask=config_mask,
            invocation_limit=payload.invocation_limit,
            invocation_window_seconds=payload.invocation_window_seconds,
            status="disabled",
            created_by=self.actor_id,
        )
        self.session.add(tool)
        await self.session.commit()
        await self.session.refresh(tool)
        return self._to_dict(tool)

    async def get_tool(self, tool_id: str) -> dict:
        tool = await self.session.get(Tool, tool_id)
        if tool is None:
            raise ApiError(404, "NOT_FOUND", "工具不存在")
        return self._to_dict(tool)

    async def update_tool(self, tool_id: str, payload) -> dict:
        tool = await self.session.get(Tool, tool_id)
        if tool is None:
            raise ApiError(404, "NOT_FOUND", "工具不存在")

        update_data = payload.model_dump(exclude_unset=True)
        if "name" in update_data and update_data["name"]:
            tool.name = update_data["name"]
        if "description" in update_data:
            tool.description = update_data["description"]
        if "config" in update_data and update_data["config"]:
            tool.config = update_data["config"]
        if "sensitive_config" in update_data and update_data["sensitive_config"]:
            try:
                tool.config_ciphertext = encrypt(update_data["sensitive_config"])
            except RuntimeError:
                raise ApiError(500, "INTERNAL_ERROR", "加密模块未初始化")
            tool.config_mask = generate_mask(update_data["sensitive_config"])
        if "invocation_limit" in update_data:
            tool.invocation_limit = update_data["invocation_limit"]
        if "invocation_window_seconds" in update_data:
            tool.invocation_window_seconds = update_data["invocation_window_seconds"]

        tool.updated_at = utc_now()
        await self.session.commit()
        await self.session.refresh(tool)
        return self._to_dict(tool)

    async def update_tool_status(self, tool_id: str, status: str) -> dict:
        if status not in ("active", "disabled"):
            raise ApiError(400, "VALIDATION_ERROR", "状态必须是 active 或 disabled")
        tool = await self.session.get(Tool, tool_id)
        if tool is None:
            raise ApiError(404, "NOT_FOUND", "工具不存在")
        tool.status = status
        tool.updated_at = utc_now()
        await self.session.commit()
        await self.session.refresh(tool)
        return self._to_dict(tool)

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------

    async def list_bound_employees(self, tool_id: str) -> list[dict]:
        binds = (
            (
                await self.session.scalars(
                    select(EmployeeToolBinding)
                    .options(selectinload(EmployeeToolBinding.employee))
                    .where(EmployeeToolBinding.tool_id == tool_id)
                )
            )
            .all()
        )
        return [
            {
                "employee_id": b.employee_id,
                "employee_name": b.employee.name if b.employee else None,
                "binding_config": b.binding_config,
                "created_at": b.created_at.isoformat() if b.created_at else None,
            }
            for b in binds
        ]

    # ------------------------------------------------------------------
    # Invocation logs
    # ------------------------------------------------------------------

    async def list_invocation_logs(
        self, tool_id: str, page: int = 1, page_size: int = 20,
    ) -> tuple[list[dict], int]:
        query = select(ToolInvocationLog).where(ToolInvocationLog.tool_id == tool_id)
        count_query = select(func.count(ToolInvocationLog.id)).where(
            ToolInvocationLog.tool_id == tool_id,
        )
        total = (await self.session.scalar(count_query)) or 0
        rows = (
            (
                await self.session.scalars(
                    query.order_by(ToolInvocationLog.created_at.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            )
            .all()
        )
        return [
            {
                "id": r.id,
                "employee_id": r.employee_id,
                "status": r.status,
                "error_code": r.error_code,
                "latency_ms": r.latency_ms,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ], total

    # ------------------------------------------------------------------
    # Execute (used by employee service)
    # ------------------------------------------------------------------

    async def execute_tool(
        self, tool_id: str, params: dict, caller_user_id: str,
        employee_id: str | None = None, message_id: str | None = None,
    ) -> dict:
        tool = await self.session.get(Tool, tool_id)
        if tool is None or tool.status != "active":
            raise ApiError(404, "NOT_FOUND", "工具不可用")

        # Rate limiting check
        cutoff = utc_now()
        import datetime
        cutoff = cutoff.replace(
            second=cutoff.second - tool.invocation_window_seconds,
        )
        recent_count = (
            await self.session.scalar(
                select(func.count(ToolInvocationLog.id)).where(
                    ToolInvocationLog.tool_id == tool_id,
                    ToolInvocationLog.caller_user_id == caller_user_id,
                    ToolInvocationLog.created_at >= cutoff,
                )
            )
        ) or 0
        if recent_count >= tool.invocation_limit:
            # Log the rate-limited attempt
            self.session.add(ToolInvocationLog(
                id=str(uuid4()),
                tool_id=tool_id,
                employee_id=employee_id,
                message_id=message_id,
                caller_user_id=caller_user_id,
                input_params=params,
                status="rate_limited",
                created_at=utc_now(),
            ))
            await self.session.commit()
            raise ApiError(429, "RATE_LIMITED", "工具调用超过频率限制")

        # Execute the tool
        log = ToolInvocationLog(
            id=str(uuid4()),
            tool_id=tool_id,
            employee_id=employee_id,
            message_id=message_id,
            caller_user_id=caller_user_id,
            input_params=params,
            status="running",
            created_at=utc_now(),
        )
        self.session.add(log)
        await self.session.flush()
        start = time.monotonic()

        try:
            output = await self._do_execute(tool, params)
            log.status = "succeeded"
            log.output_summary = str(output)[:500]
            log.latency_ms = int((time.monotonic() - start) * 1000)
            await self.session.commit()
            return output
        except Exception as e:
            log.status = "failed"
            log.error_code = "EXECUTION_ERROR"
            log.output_summary = str(e)[:500]
            log.latency_ms = int((time.monotonic() - start) * 1000)
            await self.session.commit()
            raise ApiError(502, "TOOL_ERROR", f"工具执行失败: {e}")

    async def _do_execute(self, tool: Tool, params: dict) -> dict:
        """Execute tool based on its type."""
        if tool.tool_type == "builtin_function":
            handler = _BUILTIN_HANDLERS.get(tool.code)
            if handler:
                return await handler(params)
            raise ApiError(400, "INVALID_TOOL", f"未实现的内置函数: {tool.code}")
        elif tool.tool_type == "api_call":
            return await self._execute_api_call(tool, params)
        else:
            raise ApiError(400, "INVALID_TOOL", f"不支持的工具类型: {tool.tool_type}")

    async def _execute_api_call(self, tool: Tool, params: dict) -> dict:
        """Execute an external API call tool."""
        import httpx
        url = tool.config.get("api_url", "")
        method = tool.config.get("method", "GET").upper()
        timeout = tool.config.get("timeout_seconds", 10)

        async with httpx.AsyncClient(timeout=timeout) as client:
            if method == "GET":
                resp = await client.get(url, params=params)
            elif method == "POST":
                resp = await client.post(url, json=params)
            else:
                raise ApiError(400, "INVALID_TOOL", f"不支持的 HTTP 方法: {method}")
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _to_dict(self, tool: Tool) -> dict:
        return {
            "id": tool.id,
            "code": tool.code,
            "name": tool.name,
            "description": tool.description,
            "tool_type": tool.tool_type,
            "config": tool.config,
            "config_mask": tool.config_mask,
            "invocation_limit": tool.invocation_limit,
            "invocation_window_seconds": tool.invocation_window_seconds,
            "status": tool.status,
            "created_by": tool.creator.username if tool.creator else None,
            "created_at": tool.created_at.isoformat() if tool.created_at else None,
            "updated_at": tool.updated_at.isoformat() if tool.updated_at else None,
        }


# =============================================================================
# Built-in tool handlers
# =============================================================================

_BUILTIN_HANDLERS: dict[str, callable] = {}


def register_builtin(code: str):
    """Decorator to register a built-in tool handler."""
    def wrapper(fn):
        _BUILTIN_HANDLERS[code] = fn
        return fn
    return wrapper
