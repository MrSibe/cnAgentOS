from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse

from cnagentos.api import ApiError, success_response
from cnagentos.controllers.dependencies import (
    AuthContext,
    DbSession,
    require_csrf,
    require_permission,
)
from cnagentos.schemas import (
    ConnectionTestRequest,
    ModelCallFilters,
    ModelConfigCreate,
    ModelConfigUpdate,
    StatusUpdate,
)
from cnagentos.services.model_engine import ModelEngineService


router = APIRouter(prefix="/api/v1/admin", tags=["model-engine"])
ModelViewer = Annotated[AuthContext, Depends(require_permission("models.view"))]
ModelManager = Annotated[AuthContext, Depends(require_permission("models.manage"))]
ModelTester = Annotated[AuthContext, Depends(require_permission("models.test"))]


def service_for(request: Request, session: DbSession, context: AuthContext) -> ModelEngineService:
    return ModelEngineService(
        session, context.user, request.client.host if request.client else None
    )


async def audit_on_error(
    service: ModelEngineService,
    action: str,
    target_type: str,
    target_id: str | None,
    operation: Callable[[], Awaitable[Any]],
) -> Any:
    try:
        return await operation()
    except ApiError as exc:
        await service.session.rollback()
        await service._audit(action, target_type, target_id, "failed", {"error_code": exc.code})
        await service.session.commit()
        raise


@router.get("/models")
async def list_models(
    request: Request,
    session: DbSession,
    context: ModelViewer,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    q: str | None = None,
    status: str | None = None,
):
    data, total = await service_for(request, session, context).list_models(
        page, page_size, q, status
    )
    return success_response(request, data, page=page, page_size=page_size, total=total)


@router.post("/models", dependencies=[Depends(require_csrf)])
async def create_model(
    payload: ModelConfigCreate,
    request: Request,
    session: DbSession,
    context: ModelManager,
):
    service = service_for(request, session, context)
    data = await audit_on_error(
        service, "model.created", "model_config", None, lambda: service.create_model(payload)
    )
    return success_response(request, data, status_code=201)


@router.get("/models/{model_id}")
async def get_model(
    model_id: str,
    request: Request,
    session: DbSession,
    context: ModelViewer,
):
    return success_response(request, await service_for(request, session, context).get_model(model_id))


@router.patch("/models/{model_id}", dependencies=[Depends(require_csrf)])
async def update_model(
    model_id: str,
    payload: ModelConfigUpdate,
    request: Request,
    session: DbSession,
    context: ModelManager,
):
    service = service_for(request, session, context)
    data = await audit_on_error(
        service, "model.updated", "model_config", model_id, lambda: service.update_model(model_id, payload)
    )
    return success_response(request, data)


@router.patch("/models/{model_id}/status", dependencies=[Depends(require_csrf)])
async def update_model_status(
    model_id: str,
    payload: StatusUpdate,
    request: Request,
    session: DbSession,
    context: ModelManager,
):
    service = service_for(request, session, context)
    data = await audit_on_error(
        service,
        "model.status_changed",
        "model_config",
        model_id,
        lambda: service.update_model_status(model_id, payload.status),
    )
    return success_response(request, data)


@router.put("/models/{model_id}/default", dependencies=[Depends(require_csrf)])
async def set_default_model(
    model_id: str,
    request: Request,
    session: DbSession,
    context: ModelManager,
):
    service = service_for(request, session, context)
    data = await audit_on_error(
        service,
        "model.default_changed",
        "model_config",
        model_id,
        lambda: service.set_default_model(model_id),
    )
    return success_response(request, data)


@router.post("/models/{model_id}/connection-tests", dependencies=[Depends(require_csrf)])
async def connection_test(
    model_id: str,
    payload: ConnectionTestRequest,
    request: Request,
    session: DbSession,
    context: ModelTester,
):
    if payload.stream:
        raise ApiError(400, "VALIDATION_ERROR", "流式测试请使用 /stream 端点")
    service = service_for(request, session, context)
    data = await audit_on_error(
        service,
        "model.connection_tested",
        "model_config",
        model_id,
        lambda: service.connection_test(model_id, payload),
    )
    return success_response(request, data)


@router.post("/models/{model_id}/connection-tests/stream", dependencies=[Depends(require_csrf)])
async def connection_test_stream(
    model_id: str,
    payload: ConnectionTestRequest,
    request: Request,
    session: DbSession,
    context: ModelTester,
):
    service = service_for(request, session, context)
    call_log_id, events = await service.connection_test_stream_events(model_id, payload)

    return StreamingResponse(
        events,
        media_type="text/event-stream",
        headers={
            "X-Call-Log-ID": call_log_id,
            "Cache-Control": "no-cache",
        },
    )


@router.get("/model-calls")
async def list_call_logs(
    request: Request,
    session: DbSession,
    context: ModelViewer,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    model_id: str | None = None,
    purpose: str | None = None,
    status: str | None = None,
    started_from: str | None = None,
    started_to: str | None = None,
):
    try:
        from_dt = datetime.fromisoformat(started_from) if started_from else None
        to_dt = datetime.fromisoformat(started_to) if started_to else None
    except ValueError:
        raise ApiError(400, "VALIDATION_ERROR", "请求参数无效", {"started_from": "时间格式无效"})
    filters = ModelCallFilters(
        page=page,
        page_size=page_size,
        model_id=model_id,
        purpose=purpose,
        status=status,
        started_from=from_dt,
        started_to=to_dt,
    )
    data, total = await service_for(request, session, context).list_call_logs(page, page_size, filters)
    return success_response(request, data, page=page, page_size=page_size, total=total)


@router.get("/model-calls/summary")
async def call_summary(
    request: Request,
    session: DbSession,
    context: ModelViewer,
    started_from: str | None = None,
    started_to: str | None = None,
):
    try:
        from_dt = datetime.fromisoformat(started_from) if started_from else None
        to_dt = datetime.fromisoformat(started_to) if started_to else None
    except ValueError:
        raise ApiError(400, "VALIDATION_ERROR", "请求参数无效", {"started_from": "时间格式无效"})
    return success_response(
        request, await service_for(request, session, context).call_summary(from_dt, to_dt)
    )
