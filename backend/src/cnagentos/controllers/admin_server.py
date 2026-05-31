"""Admin REST API for chat server management (Phase 7)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from cnagentos.api import success_response
from cnagentos.controllers.dependencies import (
    CurrentContext,
    DbSession,
    require_csrf,
    require_permission,
)
from cnagentos.schemas import ChatServerCreate, ChatServerUpdate, StatusUpdate
from cnagentos.services.chat_server import ChatServerService

router = APIRouter(prefix="/api/v1/admin/chat-servers", tags=["管理端-服务器管理"])

ServerAdmin = Annotated[CurrentContext, Depends(require_permission("tools.manage"))]
ServerViewer = Annotated[CurrentContext, Depends(require_permission("tools.view"))]


def service_for(request: Request, session: DbSession, context: CurrentContext) -> ChatServerService:
    return ChatServerService(
        session, context.user, request.client.host if request.client else None,
    )


@router.get("")
async def list_servers(
    request: Request,
    session: DbSession,
    context: ServerViewer,
):
    svc = service_for(request, session, context)
    data, total = await svc.list_servers()
    return success_response(request, data, page=1, page_size=20, total=total)


@router.post("", status_code=201)
async def create_server(
    request: Request,
    session: DbSession,
    context: ServerAdmin,
    payload: ChatServerCreate,
    _=Depends(require_csrf),
):
    svc = service_for(request, session, context)
    return success_response(request, await svc.create_server(payload), status_code=201)


@router.get("/{server_id}")
async def get_server(
    request: Request,
    session: DbSession,
    context: ServerViewer,
    server_id: str,
):
    svc = service_for(request, session, context)
    return success_response(request, await svc.get_server(server_id))


@router.patch("/{server_id}")
async def update_server(
    request: Request,
    session: DbSession,
    context: ServerAdmin,
    server_id: str,
    payload: ChatServerUpdate,
    _=Depends(require_csrf),
):
    svc = service_for(request, session, context)
    return success_response(request, await svc.update_server(server_id, payload))


@router.patch("/{server_id}/status")
async def update_server_status(
    request: Request,
    session: DbSession,
    context: ServerAdmin,
    server_id: str,
    payload: StatusUpdate,
    _=Depends(require_csrf),
):
    svc = service_for(request, session, context)
    return success_response(request, await svc.update_server_status(server_id, payload.status))


@router.post("/{server_id}/health-check")
async def health_check(
    request: Request,
    session: DbSession,
    context: ServerAdmin,
    server_id: str,
    _=Depends(require_csrf),
):
    svc = service_for(request, session, context)
    return success_response(request, await svc.health_check(server_id))


@router.get("/active/info")
async def get_active_server(
    request: Request,
    session: DbSession,
    context: ServerViewer,
):
    svc = service_for(request, session, context)
    result = await svc.get_active_server()
    if result is None:
        from cnagentos.api import ApiError
        raise ApiError(404, "NOT_FOUND", "没有活动的服务器")
    return success_response(request, result)


@router.post("/switch")
async def switch_server(
    request: Request,
    session: DbSession,
    context: ServerAdmin,
    server_id: str,
    _=Depends(require_csrf),
):
    svc = service_for(request, session, context)
    return success_response(request, await svc.switch_server(server_id))
