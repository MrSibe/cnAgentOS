import json
import time
from collections.abc import AsyncIterator
from datetime import datetime
from uuid import uuid4

from openai import APIConnectionError, APIStatusError, APITimeoutError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from cnagentos.api import ApiError
from cnagentos.models.entities import AuditLog, ModelCallLog, ModelConfig, User, utc_now
from cnagentos.services.model_provider import (
    InvalidModelResponse,
    ModelProviderClient,
)
from cnagentos.schemas import (
    ConnectionTestRequest,
    ModelCallFilters,
    ModelConfigCreate,
    ModelConfigUpdate,
)
from cnagentos.security import InvalidToken, decrypt, encrypt, generate_mask


VALID_MODEL_STATUSES = {"active", "disabled"}
VALID_CALL_PURPOSES = {"connection_test", "qa_answer"}
VALID_CALL_STATUSES = {"running", "succeeded", "failed"}


class ModelEngineService:
    def __init__(
        self, session: AsyncSession, actor: User, ip_address: str | None = None
    ) -> None:
        self.session = session
        self.actor = actor
        self.actor_id = actor.id
        self.ip_address = ip_address

    async def _audit(
        self,
        action: str,
        target_type: str,
        target_id: str | None,
        result: str,
        detail: dict | None = None,
    ) -> None:
        self.session.add(
            AuditLog(
                id=str(uuid4()),
                actor_user_id=self.actor_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                result=result,
                detail=detail,
                ip_address=self.ip_address,
            )
        )

    async def _serialize_model(self, model: ModelConfig) -> dict:
        return {
            "id": model.id,
            "name": model.name,
            "provider_type": model.provider_type,
            "model_name": model.model_name,
            "base_url": model.base_url,
            "credential_configured": True,
            "credential_mask": model.credential_mask,
            "status": model.status,
            "is_default": model.is_default,
            "timeout_seconds": model.timeout_seconds,
            "description": model.description,
            "created_at": model.created_at,
            "updated_at": model.updated_at,
        }

    async def list_models(
        self, page: int, page_size: int, q: str | None, status: str | None
    ) -> tuple[list[dict], int]:
        conditions = []
        if q:
            conditions.append(
                ModelConfig.name.ilike(f"%{q}%")
                | ModelConfig.model_name.ilike(f"%{q}%")
            )
        if status:
            if status not in VALID_MODEL_STATUSES:
                raise ApiError(400, "VALIDATION_ERROR", "请求参数无效", {"status": "无效状态"})
            conditions.append(ModelConfig.status == status)
        total = await self.session.scalar(
            select(func.count()).select_from(ModelConfig).where(*conditions)
        )
        models = (
            await self.session.scalars(
                select(ModelConfig)
                .where(*conditions)
                .order_by(ModelConfig.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        return [await self._serialize_model(m) for m in models], int(total or 0)

    async def create_model(self, payload: ModelConfigCreate) -> dict:
        if not payload.base_url.startswith("https://"):
            raise ApiError(400, "VALIDATION_ERROR", "请求参数无效", {"base_url": "仅支持 HTTPS 地址"})
        ciphertext = encrypt(payload.api_key)
        mask = generate_mask(payload.api_key)
        model = ModelConfig(
            id=str(uuid4()),
            name=payload.name,
            provider_type=payload.provider_type,
            model_name=payload.model_name,
            base_url=payload.base_url.rstrip("/"),
            credential_ciphertext=ciphertext,
            credential_mask=mask,
            status="disabled",
            is_default=False,
            timeout_seconds=payload.timeout_seconds,
            description=payload.description,
            created_by=self.actor_id,
        )
        self.session.add(model)
        await self._audit("model.created", "model_config", model.id, "succeeded", {"name": model.name})
        await self.session.commit()
        return await self._serialize_model(model)

    async def get_model(self, model_id: str) -> dict:
        model = await self.session.get(ModelConfig, model_id)
        if model is None:
            raise ApiError(404, "NOT_FOUND", "模型配置不存在")
        return await self._serialize_model(model)

    async def update_model(self, model_id: str, payload: ModelConfigUpdate) -> dict:
        model = await self.session.get(ModelConfig, model_id)
        if model is None:
            raise ApiError(404, "NOT_FOUND", "模型配置不存在")
        if payload.base_url is not None and not payload.base_url.startswith("https://"):
            raise ApiError(400, "VALIDATION_ERROR", "请求参数无效", {"base_url": "仅支持 HTTPS 地址"})
        if payload.name is not None:
            model.name = payload.name
        if payload.model_name is not None:
            model.model_name = payload.model_name
        if payload.base_url is not None:
            model.base_url = payload.base_url.rstrip("/")
        if payload.api_key is not None:
            model.credential_ciphertext = encrypt(payload.api_key)
            model.credential_mask = generate_mask(payload.api_key)
        if payload.timeout_seconds is not None:
            model.timeout_seconds = payload.timeout_seconds
        if "description" in payload.model_fields_set:
            model.description = payload.description
        await self._audit("model.updated", "model_config", model.id, "succeeded")
        await self.session.commit()
        return await self._serialize_model(model)

    async def update_model_status(self, model_id: str, status: str) -> dict:
        if status not in VALID_MODEL_STATUSES:
            raise ApiError(409, "INVALID_STATE", "无效的状态值", {"status": "无效状态"})
        model = await self.session.get(ModelConfig, model_id)
        if model is None:
            raise ApiError(404, "NOT_FOUND", "模型配置不存在")
        if status == "disabled" and model.is_default:
            raise ApiError(409, "INVALID_STATE", "不得停用默认模型")
        model.status = status
        await self._audit(
            "model.status_changed",
            "model_config",
            model.id,
            "succeeded",
            {"status": status},
        )
        await self.session.commit()
        return await self._serialize_model(model)

    async def set_default_model(self, model_id: str) -> dict:
        model = await self.session.get(ModelConfig, model_id)
        if model is None:
            raise ApiError(404, "NOT_FOUND", "模型配置不存在")
        if model.status != "active":
            raise ApiError(422, "MODEL_UNAVAILABLE", "默认模型必须处于启用状态")
        try:
            decrypt(model.credential_ciphertext)
        except InvalidToken:
            raise ApiError(422, "MODEL_UNAVAILABLE", "默认模型必须配置有效凭据")
        except RuntimeError:
            raise ApiError(422, "MODEL_UNAVAILABLE", "默认模型必须配置有效凭据")
        # 使用 FOR UPDATE 锁定当前默认模型，防止并发冲突
        results = (
            await self.session.scalars(
                select(ModelConfig)
                .where(ModelConfig.is_default.is_(True))
                .with_for_update()
            )
        ).all()
        for m in results:
            m.is_default = False
        model.is_default = True
        await self._audit(
            "model.default_changed",
            "model_config",
            model.id,
            "succeeded",
        )
        await self.session.commit()
        return {
            "id": model.id,
            "name": model.name,
            "is_default": model.is_default,
        }

    async def _call_model(
        self,
        model: ModelConfig,
        message: str,
        streamed: bool,
    ) -> tuple[dict, ModelCallLog]:
        call_log = ModelCallLog(
            id=str(uuid4()),
            model_config_id=model.id,
            caller_user_id=self.actor_id,
            purpose="connection_test",
            streamed=streamed,
            status="running",
            started_at=utc_now(),
        )
        self.session.add(call_log)
        await self.session.flush()
        start_time = time.monotonic()
        try:
            try:
                api_key = decrypt(model.credential_ciphertext)
            except InvalidToken:
                call_log.status = "failed"
                call_log.error_code = "INVALID_CREDENTIAL"
                call_log.finished_at = utc_now()
                call_log.latency_ms = int((time.monotonic() - start_time) * 1000)
                await self.session.commit()
                raise ApiError(422, "MODEL_UNAVAILABLE", "模型凭据无效")
            except RuntimeError:
                call_log.status = "failed"
                call_log.error_code = "CIPHER_NOT_INITIALIZED"
                call_log.finished_at = utc_now()
                call_log.latency_ms = int((time.monotonic() - start_time) * 1000)
                await self.session.commit()
                raise ApiError(500, "INTERNAL_ERROR", "加密模块未初始化")
            try:
                result = await ModelProviderClient(
                    api_key=api_key,
                    base_url=model.base_url,
                    timeout_seconds=model.timeout_seconds,
                ).complete_chat(model.model_name, message)
            except InvalidModelResponse:
                call_log.status = "failed"
                call_log.error_code = "INVALID_RESPONSE"
                call_log.latency_ms = int((time.monotonic() - start_time) * 1000)
                call_log.finished_at = utc_now()
                await self.session.commit()
                raise ApiError(502, "INVALID_RESPONSE", "上游返回了无效的响应格式")
            except APIStatusError:
                call_log.status = "failed"
                call_log.error_code = "UPSTREAM_ERROR"
                call_log.latency_ms = int((time.monotonic() - start_time) * 1000)
                call_log.finished_at = utc_now()
                await self.session.commit()
                raise ApiError(502, "UPSTREAM_ERROR", "模型服务返回错误")
            call_log.latency_ms = int((time.monotonic() - start_time) * 1000)
            call_log.finished_at = utc_now()
            call_log.status = "succeeded"
            call_log.prompt_tokens = result.usage.prompt_tokens
            call_log.completion_tokens = result.usage.completion_tokens
            call_log.total_tokens = result.usage.total_tokens
            return {
                "reply": result.reply,
                "usage": {
                    "prompt_tokens": call_log.prompt_tokens,
                    "completion_tokens": call_log.completion_tokens,
                    "total_tokens": call_log.total_tokens,
                },
            }, call_log
        except APITimeoutError:
            call_log.status = "failed"
            call_log.error_code = "TIMEOUT"
            call_log.finished_at = utc_now()
            call_log.latency_ms = int((time.monotonic() - start_time) * 1000)
            await self.session.commit()
            raise ApiError(504, "TIMEOUT", "模型服务响应超时")
        except APIConnectionError as exc:
            call_log.status = "failed"
            call_log.error_code = "CONNECTION_ERROR"
            call_log.finished_at = utc_now()
            call_log.latency_ms = int((time.monotonic() - start_time) * 1000)
            await self.session.commit()
            raise ApiError(502, "CONNECTION_ERROR", f"无法连接到模型服务: {type(exc).__name__}")

    def _stream_error_event(self, code: str, message: str) -> str:
        payload = {"event": "error", "error": {"code": code, "message": message}}
        return f"event: error\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

    async def _finalize_stream_call(
        self,
        call_log: ModelCallLog,
        start_time: float,
        status: str,
        error_code: str | None = None,
    ) -> None:
        call_log.status = status
        call_log.error_code = error_code
        call_log.latency_ms = int((time.monotonic() - start_time) * 1000)
        call_log.finished_at = utc_now()
        await self.session.commit()

    async def connection_test_stream_events(
        self, model_id: str, payload: ConnectionTestRequest
    ) -> tuple[str, AsyncIterator[str]]:
        model = await self.session.get(ModelConfig, model_id)
        if model is None:
            raise ApiError(404, "NOT_FOUND", "模型配置不存在")
        if model.status != "active":
            raise ApiError(409, "INVALID_STATE", "模型未启用，无法测试")
        try:
            api_key = decrypt(model.credential_ciphertext)
        except InvalidToken:
            raise ApiError(422, "MODEL_UNAVAILABLE", "模型凭据无效")
        except RuntimeError:
            raise ApiError(500, "INTERNAL_ERROR", "加密模块未初始化")
        call_log = ModelCallLog(
            id=str(uuid4()),
            model_config_id=model.id,
            caller_user_id=self.actor_id,
            purpose="connection_test",
            streamed=True,
            status="running",
            started_at=utc_now(),
        )
        self.session.add(call_log)
        await self.session.flush()
        start_time = time.monotonic()

        async def generate() -> AsyncIterator[str]:
            try:
                async for chunk in ModelProviderClient(
                    api_key=api_key,
                    base_url=model.base_url,
                    timeout_seconds=model.timeout_seconds,
                ).stream_chat(model.model_name, payload.message):
                    yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                await self._finalize_stream_call(call_log, start_time, "succeeded")
                usage = {
                    "prompt_tokens": call_log.prompt_tokens,
                    "completion_tokens": call_log.completion_tokens,
                    "total_tokens": call_log.total_tokens,
                }
                yield f"data: {json.dumps({'event': 'completed', 'call_log_id': call_log.id, 'usage': usage}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
            except APIStatusError as exc:
                error_code = f"HTTP_{exc.status_code}"
                await self._finalize_stream_call(call_log, start_time, "failed", error_code)
                yield self._stream_error_event(error_code, "上游模型服务返回错误")
                yield "data: [DONE]\n\n"
            except APITimeoutError:
                await self._finalize_stream_call(call_log, start_time, "failed", "TIMEOUT")
                yield self._stream_error_event("TIMEOUT", "模型服务响应超时")
                yield "data: [DONE]\n\n"
            except APIConnectionError:
                await self._finalize_stream_call(call_log, start_time, "failed", "CONNECTION_ERROR")
                yield self._stream_error_event("CONNECTION_ERROR", "无法连接到模型服务")
                yield "data: [DONE]\n\n"
            except Exception:
                await self._finalize_stream_call(call_log, start_time, "failed", "UPSTREAM_ERROR")
                yield self._stream_error_event("UPSTREAM_ERROR", "流式响应出错")
                yield "data: [DONE]\n\n"
            finally:
                if call_log.status == "running":
                    call_log.status = "failed"
                    call_log.error_code = "CLIENT_DISCONNECTED"
                    call_log.finished_at = utc_now()
                    try:
                        await self.session.commit()
                    except Exception:
                        pass

        return call_log.id, generate()

    async def connection_test(
        self, model_id: str, payload: ConnectionTestRequest
    ) -> dict:
        model = await self.session.get(ModelConfig, model_id)
        if model is None:
            raise ApiError(404, "NOT_FOUND", "模型配置不存在")
        if model.status != "active":
            raise ApiError(409, "INVALID_STATE", "模型未启用，无法测试")
        result, call_log = await self._call_model(model, payload.message, payload.stream)
        await self.session.commit()
        return {
            "call_log_id": call_log.id,
            "reply": result["reply"],
            "usage": result["usage"],
            "latency_ms": call_log.latency_ms,
        }

    async def list_call_logs(
        self, page: int, page_size: int, filters: ModelCallFilters
    ) -> tuple[list[dict], int]:
        conditions = []
        if filters.model_id:
            conditions.append(ModelCallLog.model_config_id == filters.model_id)
        if filters.purpose:
            if filters.purpose not in VALID_CALL_PURPOSES:
                raise ApiError(400, "VALIDATION_ERROR", "请求参数无效", {"purpose": "无效用途"})
            conditions.append(ModelCallLog.purpose == filters.purpose)
        if filters.status:
            if filters.status not in VALID_CALL_STATUSES:
                raise ApiError(400, "VALIDATION_ERROR", "请求参数无效", {"status": "无效状态"})
            conditions.append(ModelCallLog.status == filters.status)
        if filters.started_from:
            conditions.append(ModelCallLog.started_at >= filters.started_from)
        if filters.started_to:
            conditions.append(ModelCallLog.started_at <= filters.started_to)
        total = await self.session.scalar(
            select(func.count()).select_from(ModelCallLog).where(*conditions)
        )
        logs = (
            await self.session.scalars(
                select(ModelCallLog)
                .options(selectinload(ModelCallLog.model_config))
                .where(*conditions)
                .order_by(ModelCallLog.started_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        data = []
        for log in logs:
            model = log.model_config if log.model_config_id else None
            data.append({
                "id": log.id,
                "model": {"id": model.id, "name": model.name} if model else None,
                "purpose": log.purpose,
                "streamed": log.streamed,
                "status": log.status,
                "prompt_tokens": log.prompt_tokens,
                "completion_tokens": log.completion_tokens,
                "total_tokens": log.total_tokens,
                "latency_ms": log.latency_ms,
                "error_code": log.error_code,
                "started_at": log.started_at,
                "finished_at": log.finished_at,
            })
        return data, int(total or 0)

    async def call_summary(
        self,
        started_from: datetime | None,
        started_to: datetime | None,
    ) -> dict:
        conditions = []
        if started_from:
            conditions.append(ModelCallLog.started_at >= started_from)
        if started_to:
            conditions.append(ModelCallLog.started_at <= started_to)
        stmt = (
            select(
                ModelCallLog.status,
                func.count(ModelCallLog.id).label("count"),
                func.sum(ModelCallLog.total_tokens).label("total_tokens"),
                func.avg(ModelCallLog.latency_ms).label("avg_latency"),
            )
            .where(*conditions)
            .group_by(ModelCallLog.status)
        )
        result = await self.session.execute(stmt)
        rows = result.all()
        total_calls = 0
        succeeded_calls = 0
        failed_calls = 0
        total_tokens = 0
        avg_latency = 0
        latency_sum = 0
        latency_count = 0
        for row in rows:
            total_calls += row.count
            if row.status == "succeeded":
                succeeded_calls = row.count
                if row.total_tokens:
                    total_tokens = row.total_tokens
            elif row.status == "failed":
                failed_calls = row.count
            if row.avg_latency is not None:
                latency_sum += row.avg_latency * row.count
                latency_count += row.count
        if latency_count > 0:
            avg_latency = int(latency_sum / latency_count)
        return {
            "total_calls": total_calls,
            "succeeded_calls": succeeded_calls,
            "failed_calls": failed_calls,
            "total_tokens": total_tokens,
            "avg_latency_ms": avg_latency,
        }
