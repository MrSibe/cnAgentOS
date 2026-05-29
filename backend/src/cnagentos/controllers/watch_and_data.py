"""
Watch and Data API controllers.

Provides endpoints for data sources, rules, collection tasks, and knowledge items.
"""

import logging
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
from cnagentos.models.entities import CollectionTask
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

logger = logging.getLogger(__name__)

_background_tasks: list = []


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
    operation: Callable[[], Awaitable[Any]],
) -> Any:
    try:
        return await operation()
    except ApiError as exc:
        await service.session.rollback()
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
    try:
        data = await service.create_source(payload)
        await session.commit()
        return success_response(request, data, status_code=201)
    except ApiError:
        await session.rollback()
        raise


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
    try:
        data = await service.update_source(source_id, payload)
        await session.commit()
        return success_response(request, data)
    except ApiError:
        await session.rollback()
        raise


@router.patch("/watch-sources/{source_id}/status", dependencies=[Depends(require_csrf)])
async def update_source_status(
    source_id: str,
    payload: StatusUpdate,
    request: Request,
    session: DbSession,
    context: WatchSourceManager,
):
    service = service_for(request, session, context)
    try:
        data = await service.update_source_status(source_id, payload.status)
        await session.commit()
        return success_response(request, data)
    except ApiError:
        await session.rollback()
        raise


# --- Watch Rules ---
@router.get("/watch-sources/{source_id}/rules")
async def list_rules(
    source_id: str,
    request: Request,
    session: DbSession,
    context: WatchSourceManager,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    data, total = await service_for(request, session, context).list_rules(source_id, page, page_size)
    return success_response(request, data, total=total, page=page, page_size=page_size)


@router.post("/watch-sources/{source_id}/rules", dependencies=[Depends(require_csrf)])
async def create_rule(
    source_id: str,
    payload: WatchRuleCreate,
    request: Request,
    session: DbSession,
    context: WatchSourceManager,
):
    service = service_for(request, session, context)
    try:
        data = await service.create_rule(source_id, payload)
        await session.commit()
        return success_response(request, data, status_code=201)
    except ApiError:
        await session.rollback()
        raise


@router.patch("/watch-rules/{rule_id}", dependencies=[Depends(require_csrf)])
async def update_rule(
    rule_id: str,
    payload: WatchRuleUpdate,
    request: Request,
    session: DbSession,
    context: WatchSourceManager,
):
    service = service_for(request, session, context)
    try:
        data = await service.update_rule(rule_id, payload)
        await session.commit()
        return success_response(request, data)
    except ApiError:
        await session.rollback()
        raise


# --- Collection Tasks ---
@router.post("/collection-tasks", dependencies=[Depends(require_csrf)])
async def create_task(
    payload: CollectionTaskCreate,
    request: Request,
    session: DbSession,
    context: WatchTaskRunner,
):
    service = service_for(request, session, context)
    try:
        data = await service.create_task(payload)
        await session.commit()
        return success_response(request, data, status_code=202)
    except ApiError:
        await session.rollback()
        raise


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
    try:
        data = await service.cancel_task(task_id)
        await session.commit()
        return success_response(request, data)
    except ApiError:
        await session.rollback()
        raise


@router.post("/collection-tasks/{task_id}/execute", dependencies=[Depends(require_csrf)])
async def run_task(
    task_id: str,
    request: Request,
    session: DbSession,
    context: WatchTaskRunner,
):
    task = await session.get(CollectionTask, task_id)
    if task is None:
        raise ApiError(404, "NOT_FOUND", "任务不存在")
    if task.status != "pending":
        raise ApiError(409, "INVALID_STATE", "只能执行待执行状态的任务")

    await session.commit()

    import asyncio
    from cnagentos.app import app as fastapi_app
    sessionmaker = fastapi_app.state.sessionmaker
    task = asyncio.create_task(_execute_task_background(task_id, sessionmaker))
    _background_tasks.append(task)
    task.add_done_callback(lambda t: _background_tasks.remove(t) if t in _background_tasks else None)

    return success_response(request, {"id": task_id, "status": task.status})


async def _execute_task_background(task_id: str, sessionmaker) -> None:
    """Background task that creates its own session."""
    from cnagentos.services.watch_and_data import WatchService
    from cnagentos.services.bootstrap import ensure_system_task_user
    async with sessionmaker() as session:
        try:
            actor = await ensure_system_task_user(session)
            service = WatchService(session, actor, None)
            await service.execute_task(task_id)
        except Exception:
            logger.exception("Background task %s failed", task_id)


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
    try:
        data = await service.update_knowledge_item_status(item_id, payload.status)
        await session.commit()
        return success_response(request, data)
    except ApiError:
        await session.rollback()
        raise
