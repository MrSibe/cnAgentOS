"""Digital Employee service — CRUD, tool binding, multi-turn context, LLM orchestration."""

import re
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from cnagentos.api import ApiError
from cnagentos.models.entities import (
    DigitalEmployee,
    EmployeeToolBinding,
    Message,
    ModelCallLog,
    ModelConfig,
    Tool,
    User,
    utc_now,
)
from cnagentos.security import decrypt


MENTION_PATTERN = re.compile(r"@(\S+)")


class DigitalEmployeeService:
    """Manage digital employees, tool bindings, and LLM-powered responses."""

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

    async def list_employees(
        self, page: int = 1, page_size: int = 20,
        q: str | None = None, status: str | None = None,
    ) -> tuple[list[dict], int]:
        query = select(DigitalEmployee)
        count_query = select(func.count(DigitalEmployee.id))
        if q:
            pattern = f"%{q}%"
            query = query.where(DigitalEmployee.name.ilike(pattern))
            count_query = count_query.where(DigitalEmployee.name.ilike(pattern))
        if status:
            query = query.where(DigitalEmployee.status == status)
            count_query = count_query.where(DigitalEmployee.status == status)

        total = (await self.session.scalar(count_query)) or 0
        rows = (
            (
                await self.session.scalars(
                    query.options(
                        selectinload(DigitalEmployee.model_config),
                        selectinload(DigitalEmployee.creator),
                    )
                    .order_by(DigitalEmployee.created_at.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            )
            .all()
        )
        return [self._to_dict(emp, include_prompt=False) for emp in rows], total

    async def list_active_employees(self) -> list[dict]:
        """List employees that are active and available for @mention. (User-side)"""
        rows = (
            (
                await self.session.scalars(
                    select(DigitalEmployee)
                    .where(DigitalEmployee.status == "active")
                    .order_by(DigitalEmployee.created_at.asc())
                )
            )
            .all()
        )
        return [self._to_dict(emp, include_prompt=False) for emp in rows]

    async def create_employee(self, payload) -> dict:
        code = payload.code.strip()
        existing = await self.session.scalar(
            select(DigitalEmployee).where(DigitalEmployee.code == code),
        )
        if existing:
            raise ApiError(409, "CONFLICT", f"员工代码已存在: {code}")

        if payload.model_config_id:
            mc = await self.session.get(ModelConfig, payload.model_config_id)
            if mc is None or mc.status != "active":
                raise ApiError(400, "INVALID_MODEL", "指定的模型配置不可用")

        emp = DigitalEmployee(
            id=str(uuid4()),
            code=code,
            name=payload.name,
            avatar=payload.avatar,
            description=payload.description,
            system_prompt=payload.system_prompt,
            model_config_id=payload.model_config_id,
            trigger_type=payload.trigger_type,
            max_turns=payload.max_turns,
            status="disabled",
            created_by=self.actor_id,
        )
        self.session.add(emp)
        await self.session.commit()
        await self.session.refresh(emp)
        return self._to_dict(emp, include_prompt=True)

    async def get_employee(self, employee_id: str) -> dict:
        emp = await self.session.get(
            DigitalEmployee, employee_id,
            options=[
                selectinload(DigitalEmployee.model_config),
                selectinload(DigitalEmployee.creator),
            ],
        )
        if emp is None:
            raise ApiError(404, "NOT_FOUND", "数字员工不存在")
        return self._to_dict(emp, include_prompt=True)

    async def update_employee(self, employee_id: str, payload) -> dict:
        emp = await self.session.get(DigitalEmployee, employee_id)
        if emp is None:
            raise ApiError(404, "NOT_FOUND", "数字员工不存在")

        update_data = payload.model_dump(exclude_unset=True)
        if "name" in update_data:
            emp.name = update_data["name"]
        if "avatar" in update_data:
            emp.avatar = update_data["avatar"]
        if "description" in update_data:
            emp.description = update_data["description"]
        if "system_prompt" in update_data:
            emp.system_prompt = update_data["system_prompt"]
        if "model_config_id" in update_data:
            if update_data["model_config_id"]:
                mc = await self.session.get(ModelConfig, update_data["model_config_id"])
                if mc is None or mc.status != "active":
                    raise ApiError(400, "INVALID_MODEL", "指定的模型配置不可用")
            emp.model_config_id = update_data["model_config_id"]
        if "trigger_type" in update_data:
            emp.trigger_type = update_data["trigger_type"]
        if "max_turns" in update_data:
            emp.max_turns = update_data["max_turns"]

        emp.updated_at = utc_now()
        await self.session.commit()
        await self.session.refresh(emp)
        return self._to_dict(emp, include_prompt=True)

    async def update_employee_status(self, employee_id: str, status: str) -> dict:
        if status not in ("active", "disabled"):
            raise ApiError(400, "VALIDATION_ERROR", "状态必须是 active 或 disabled")
        emp = await self.session.get(DigitalEmployee, employee_id)
        if emp is None:
            raise ApiError(404, "NOT_FOUND", "数字员工不存在")
        emp.status = status
        emp.updated_at = utc_now()
        await self.session.commit()
        await self.session.refresh(emp)
        return self._to_dict(emp, include_prompt=False)

    # ------------------------------------------------------------------
    # Tool binding
    # ------------------------------------------------------------------

    async def list_bound_tools(self, employee_id: str) -> list[dict]:
        binds = (
            (
                await self.session.scalars(
                    select(EmployeeToolBinding)
                    .options(selectinload(EmployeeToolBinding.tool))
                    .where(EmployeeToolBinding.employee_id == employee_id)
                )
            )
            .all()
        )
        return [
            {
                "tool_id": b.tool_id,
                "tool_code": b.tool.code if b.tool else None,
                "tool_name": b.tool.name if b.tool else None,
                "tool_type": b.tool.tool_type if b.tool else None,
                "binding_config": b.binding_config,
                "created_at": b.created_at.isoformat() if b.created_at else None,
            }
            for b in binds
        ]

    async def bind_tool(self, employee_id: str, tool_id: str, binding_config: dict | None = None) -> dict:
        emp = await self.session.get(DigitalEmployee, employee_id)
        if emp is None:
            raise ApiError(404, "NOT_FOUND", "数字员工不存在")
        tool = await self.session.get(Tool, tool_id)
        if tool is None:
            raise ApiError(404, "NOT_FOUND", "工具不存在")

        existing = await self.session.get(
            EmployeeToolBinding, (employee_id, tool_id),
        )
        if existing:
            raise ApiError(409, "CONFLICT", "该工具已绑定到此员工")

        bind = EmployeeToolBinding(
            employee_id=employee_id, tool_id=tool_id,
            binding_config=binding_config,
        )
        self.session.add(bind)
        await self.session.commit()
        return {"employee_id": employee_id, "tool_id": tool_id}

    async def unbind_tool(self, employee_id: str, tool_id: str) -> None:
        bind = await self.session.get(
            EmployeeToolBinding, (employee_id, tool_id),
        )
        if bind is None:
            raise ApiError(404, "NOT_FOUND", "绑定关系不存在")
        await self.session.delete(bind)
        await self.session.commit()

    # ------------------------------------------------------------------
    # Call logs
    # ------------------------------------------------------------------

    async def list_call_logs(
        self, employee_id: str, page: int = 1, page_size: int = 20,
    ) -> tuple[list[dict], int]:
        from cnagentos.models.entities import ToolInvocationLog

        query = select(ToolInvocationLog).where(
            ToolInvocationLog.employee_id == employee_id,
        )
        count_query = select(func.count(ToolInvocationLog.id)).where(
            ToolInvocationLog.employee_id == employee_id,
        )
        total = (await self.session.scalar(count_query)) or 0
        rows = (
            (
                await self.session.scalars(
                    query.options(
                        selectinload(ToolInvocationLog.tool),
                        selectinload(ToolInvocationLog.caller),
                    )
                    .order_by(ToolInvocationLog.created_at.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            )
            .all()
        )
        return [
            {
                "id": r.id,
                "tool_name": r.tool.name if r.tool else None,
                "caller_name": r.caller.username if r.caller else None,
                "status": r.status,
                "error_code": r.error_code,
                "latency_ms": r.latency_ms,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ], total

    # ------------------------------------------------------------------
    # @mention detection
    # ------------------------------------------------------------------

    async def detect_mentions(self, content: str) -> list[dict]:
        """Scan message content for @EmployeeName patterns and return matched employees."""
        mentions = MENTION_PATTERN.findall(content)
        if not mentions:
            return []

        active_emps = (
            (
                await self.session.scalars(
                    select(DigitalEmployee).where(DigitalEmployee.status == "active")
                )
            )
            .all()
        )
        results = []
        for mention in mentions:
            for emp in active_emps:
                if mention == emp.name:
                    results.append(self._to_dict(emp, include_prompt=True))
                    break
        return results

    # ------------------------------------------------------------------
    # LLM invocation
    # ------------------------------------------------------------------

    async def invoke_employee(
        self, employee_id: str, conversation_id: str,
        user_message_content: str, content_type: str = "text",
    ) -> dict:
        """Invoke the digital employee to generate a reply in a conversation."""
        emp = await self.session.get(DigitalEmployee, employee_id)
        if emp is None or emp.status != "active":
            raise ApiError(404, "NOT_FOUND", "数字员工不可用")

        # Build conversation context
        context_messages = await self._build_context(emp, conversation_id)

        # Add user message
        context_messages.append({"role": "user", "content": user_message_content})

        # Determine model config
        model_config_id = emp.model_config_id
        if not model_config_id:
            # Fallback to default model
            default = await self.session.scalar(
                select(ModelConfig).where(
                    ModelConfig.status == "active",
                    ModelConfig.is_default == True,  # noqa: E712
                )
            )
            if default is None:
                raise ApiError(422, "MODEL_UNAVAILABLE", "没有可用的默认模型")
            model_config_id = default.id

        model_config = await self.session.get(ModelConfig, model_config_id)
        if model_config is None or model_config.status != "active":
            raise ApiError(422, "MODEL_UNAVAILABLE", "绑定的模型不可用")

        # Decrypt API key
        try:
            api_key = decrypt(model_config.credential_ciphertext)
        except Exception:
            raise ApiError(422, "MODEL_UNAVAILABLE", "模型凭据无效")

        # Call LLM
        from cnagentos.services.model_provider import ModelProviderClient

        client = ModelProviderClient(
            api_key=api_key,
            base_url=model_config.base_url,
            timeout_seconds=model_config.timeout_seconds,
        )

        # Create model call log
        call_log = ModelCallLog(
            id=str(uuid4()),
            model_config_id=model_config.id,
            caller_user_id=self.actor_id,
            purpose="employee_chat",
            related_id=conversation_id,
            streamed=False,
            status="running",
            started_at=utc_now(),
        )
        self.session.add(call_log)
        await self.session.flush()

        import time
        start = time.monotonic()
        reply = ""
        try:
            response = await client.complete_chat_with_messages(
                model_config.model_name, context_messages,
            )
            reply = response.reply
            call_log.status = "succeeded"
            call_log.prompt_tokens = response.usage.prompt_tokens
            call_log.completion_tokens = response.usage.completion_tokens
            call_log.total_tokens = response.usage.total_tokens
        except Exception as e:
            reply = f"抱歉，我暂时无法回复: {e}"
            call_log.status = "failed"
            call_log.error_code = "LLM_ERROR"
        finally:
            call_log.latency_ms = int((time.monotonic() - start) * 1000)
            call_log.finished_at = utc_now()
            await self.session.commit()

        return {"reply": reply, "employee_id": emp.id, "employee_name": emp.name}

    async def _build_context(
        self, emp: DigitalEmployee, conversation_id: str,
    ) -> list[dict]:
        """Build message context list from conversation history."""
        messages = [{"role": "system", "content": emp.system_prompt}]

        # Fetch recent messages from conversation
        recent = (
            (
                await self.session.scalars(
                    select(Message)
                    .options(selectinload(Message.sender))
                    .where(Message.conversation_id == conversation_id)
                    .order_by(Message.created_at.desc())
                    .limit(emp.max_turns)
                )
            )
            .all()
        )
        for msg in reversed(recent):
            role = "user" if msg.sender_id != "system" else "system"
            messages.append({"role": role, "content": msg.content})

        return messages

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _to_dict(self, emp: DigitalEmployee, include_prompt: bool = False) -> dict:
        d = {
            "id": emp.id,
            "code": emp.code,
            "name": emp.name,
            "avatar": emp.avatar,
            "description": emp.description,
            "model_config_id": emp.model_config_id,
            "model_name": emp.model_config.model_name if emp.model_config else None,
            "trigger_type": emp.trigger_type,
            "max_turns": emp.max_turns,
            "status": emp.status,
            "created_by": emp.creator.username if emp.creator else None,
            "created_at": emp.created_at.isoformat() if emp.created_at else None,
            "updated_at": emp.updated_at.isoformat() if emp.updated_at else None,
        }
        if include_prompt:
            d["system_prompt"] = emp.system_prompt
        return d
