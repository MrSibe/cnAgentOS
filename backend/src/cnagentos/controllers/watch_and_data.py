"""
Watch and Data API controllers.

Provides endpoints for data sources, rules, collection tasks, and knowledge items.
"""

from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request

from cnagentos.api import ApiError, success_response
from cnagentos.controllers.dependencies import (
    AuthContext,
    DbSession,
    require_csrf,
    require_permission,
)
from cnagentos.schemas import (
    CollectionTaskCreate,
    KnowledgeItemFilters,
    StatusUpdate,
    WatchRuleCreate,
    WatchRuleUpdate,
    WatchSourceCreate,
    WatchSourceUpdate,
)
from cnagentos.services.watch_and_data import WatchService


router = APIRouter(prefix="/api/v1/admin", tags=["watch-and-data"])
WatchSourceManager = Annotated[AuthContext, Depends(require_permission("watch.sources.manage"))]
WatchTaskRunner = Annotated[AuthContext, Depends(require_permission("watch.tasks.run"))]
WatchTaskViewer = Annotated[AuthContext, Depends(require_permission("watch.tasks.view"))]
DataItemViewer = Annotated[AuthContext, Depends(require_permission("data.items.view"))]
DataItemManager = Annotated[AuthContext, Depends(require_permission("data.items.manage"))]


def service_for(request: Request, session: DbSession, context: AuthContext) -> WatchService:
    return WatchService(
        session, context.user, request.client.host if request.client else None
    )


async def audit_on_error(
    service: WatchService,
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


# --- Data Sources ---
@router.get("/watch-sources")
async def list_sources(
    request: Request,
    session: DbSession,
    context: WatchSourceManager,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    q: str | None = None,
    status: str | None = None,
    source_type: str | None = None,
):
    data, total = await service_for(request, session, context).list_sources(
        page, page_size, q, status, source_type
    )
    return success_response(request, data, page=page, page_size=page_size, total=total)


@router.post("/watch-sources", dependencies=[Depends(require_csrf)])
async def create_source(
    payload: WatchSourceCreate,
    request: Request,
    session: DbSession,
    context: WatchSourceManager,
):
    service = service_for(request, session, context)
    data = await audit_on_error(
        service, "watch.source.created", "watch_source", None, lambda: service.create_source(payload)
    )
    return success_response(request, data, status_code=201)


@router.get("/watch-sources/{source_id}")
async def get_source(
    source_id: str,
    request: Request,
    session: DbSession,
    context: WatchSourceManager,
):
    return success_response(request, await service_for(request, session, context).get_source(source_id))


@router.patch("/watch-sources/{source_id}", dependencies=[Depends(require_csrf)])
async def update_source(
    source_id: str,
    payload: WatchSourceUpdate,
    request: Request,
    session: DbSession,
    context: WatchSourceManager,
):
    service = service_for(request, session, context)
    data = await audit_on_error(
        service, "watch.source.updated", "watch_source", source_id, lambda: service.update_source(source_id, payload)
    )
    return success_response(request, data)


@router.patch("/watch-sources/{source_id}/status", dependencies=[Depends(require_csrf)])
async def update_source_status(
    source_id: str,
    payload: StatusUpdate,
    request: Request,
    session: DbSession,
    context: WatchSourceManager,
):
    service = service_for(request, session, context)
    data = await audit_on_error(
        service,
        "watch.source.status_changed",
        "watch_source",
        source_id,
        lambda: service.update_source_status(source_id, payload.status),
    )
    return success_response(request, data)


# --- Watch Rules ---
@router.get("/watch-sources/{source_id}/rules")
async def list_rules(
    source_id: str,
    request: Request,
    session: DbSession,
    context: WatchSourceManager,
):
    return success_response(request, await service_for(request, session, context).list_rules(source_id))


@router.post("/watch-sources/{source_id}/rules", dependencies=[Depends(require_csrf)])
async def create_rule(
    source_id: str,
    payload: WatchRuleCreate,
    request: Request,
    session: DbSession,
    context: WatchSourceManager,
):
    service = service_for(request, session, context)
    data = await audit_on_error(
        service, "watch.rule.created", "watch_rule", None, lambda: service.create_rule(source_id, payload)
    )
    return success_response(request, data, status_code=201)


@router.patch("/watch-rules/{rule_id}", dependencies=[Depends(require_csrf)])
async def update_rule(
    rule_id: str,
    payload: WatchRuleUpdate,
    request: Request,
    session: DbSession,
    context: WatchSourceManager,
):
    service = service_for(request, session, context)
    data = await audit_on_error(
        service, "watch.rule.updated", "watch_rule", rule_id, lambda: service.update_rule(rule_id, payload)
    )
    return success_response(request, data)


# --- Collection Tasks ---
@router.post("/collection-tasks", dependencies=[Depends(require_csrf)])
async def create_task(
    payload: CollectionTaskCreate,
    request: Request,
    session: DbSession,
    context: WatchTaskRunner,
):
    service = service_for(request, session, context)
    data = await audit_on_error(
        service, "watch.task.created", "collection_task", None, lambda: service.create_task(payload)
    )
    return success_response(request, data, status_code=202)


@router.get("/collection-tasks")
async def list_tasks(
    request: Request,
    session: DbSession,
    context: WatchTaskViewer,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = None,
    started_from: str | None = None,
    started_to: str | None = None,
):
    try:
        from_dt = datetime.fromisoformat(started_from) if started_from else None
        to_dt = datetime.fromisoformat(started_to) if started_to else None
    except ValueError:
        raise ApiError(400, "VALIDATION_ERROR", "请求参数无效", {"started_from": "时间格式无效"})
    data, total = await service_for(request, session, context).list_tasks(
        page, page_size, status, from_dt, to_dt
    )
    return success_response(request, data, page=page, page_size=page_size, total=total)


@router.get("/collection-tasks/{task_id}")
async def get_task(
    task_id: str,
    request: Request,
    session: DbSession,
    context: WatchTaskViewer,
):
    return success_response(request, await service_for(request, session, context).get_task(task_id))


@router.post("/collection-tasks/{task_id}/cancel", dependencies=[Depends(require_csrf)])
async def cancel_task(
    task_id: str,
    request: Request,
    session: DbSession,
    context: WatchTaskRunner,
):
    service = service_for(request, session, context)
    data = await audit_on_error(
        service, "watch.task.cancelled", "collection_task", task_id, lambda: service.cancel_task(task_id)
    )
    return success_response(request, data)


# --- Knowledge Items ---
@router.get("/knowledge-items")
async def list_knowledge_items(
    request: Request,
    session: DbSession,
    context: DataItemViewer,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    q: str | None = None,
    source_id: str | None = None,
    status: str | None = None,
    collected_from: str | None = None,
    collected_to: str | None = None,
):
    try:
        collected_from_dt = datetime.fromisoformat(collected_from) if collected_from else None
        collected_to_dt = datetime.fromisoformat(collected_to) if collected_to else None
    except ValueError:
        raise ApiError(400, "VALIDATION_ERROR", "请求参数无效", {"collected_from": "时间格式无效"})

    filters = KnowledgeItemFilters(
        source_id=source_id,
        status=status,
        collected_from=collected_from_dt,
        collected_to=collected_to_dt,
    )
    data, total = await service_for(request, session, context).list_knowledge_items(
        page, page_size, q, filters
    )
    return success_response(request, data, page=page, page_size=page_size, total=total)


@router.get("/knowledge-items/{item_id}")
async def get_knowledge_item(
    item_id: str,
    request: Request,
    session: DbSession,
    context: DataItemViewer,
):
    return success_response(request, await service_for(request, session, context).get_knowledge_item(item_id))


@router.patch("/knowledge-items/{item_id}/status", dependencies=[Depends(require_csrf)])
async def update_knowledge_item_status(
    item_id: str,
    payload: StatusUpdate,
    request: Request,
    session: DbSession,
    context: DataItemManager,
):
    service = service_for(request, session, context)
    data = await audit_on_error(
        service,
        "data.item.status_changed",
        "knowledge_item",
        item_id,
        lambda: service.update_knowledge_item_status(item_id, payload.status),
    )
    return success_response(request, data)
