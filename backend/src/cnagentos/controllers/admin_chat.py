"""Admin REST API for group management and file management (Phase 7)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from cnagentos.api import success_response
from cnagentos.controllers.dependencies import (
    CurrentContext,
    DbSession,
    require_csrf,
    require_permission,
)
from cnagentos.schemas import BanMemberRequest, GroupAnnouncementCreate
from cnagentos.services.chat import ChatService
from cnagentos.services.file import FileService

router = APIRouter(prefix="/api/v1/admin", tags=["管理端-聊天"])

# Permission-guarded dependency aliases
GroupAdmin = Annotated[CurrentContext, Depends(require_permission("chat.groups.manage"))]
FileViewer = Annotated[CurrentContext, Depends(require_permission("files.view"))]
FileManager = Annotated[CurrentContext, Depends(require_permission("files.manage"))]


def chat_service(request: Request, session: DbSession, context: CurrentContext) -> ChatService:
    return ChatService(
        session, context.user, request.client.host if request.client else None,
    )


def file_service(request: Request, session: DbSession, context: CurrentContext) -> FileService:
    return FileService(
        session, context.user, request.client.host if request.client else None,
    )


# =============================================================================
# Group management
# =============================================================================


@router.get("/chat/groups")
async def list_groups(
    request: Request,
    session: DbSession,
    context: GroupAdmin,
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    svc = chat_service(request, session, context)
    data, total = await svc.list_all_groups(page, page_size, q)
    return success_response(request, data, page=page, page_size=page_size, total=total)


@router.get("/chat/groups/{conversation_id}")
async def get_group_detail(
    request: Request,
    session: DbSession,
    context: GroupAdmin,
    conversation_id: str,
):
    svc = chat_service(request, session, context)
    return success_response(request, await svc.get_group_detail(conversation_id))


@router.get("/chat/groups/{conversation_id}/members")
async def get_group_members(
    request: Request,
    session: DbSession,
    context: GroupAdmin,
    conversation_id: str,
):
    svc = chat_service(request, session, context)
    return success_response(request, await svc.get_conversation_members(conversation_id))


@router.patch("/chat/groups/{conversation_id}/disband")
async def disband_group(
    request: Request,
    session: DbSession,
    context: GroupAdmin,
    conversation_id: str,
    _=Depends(require_csrf),
):
    svc = chat_service(request, session, context)
    await svc.disband_group(conversation_id)
    return success_response(request, None)


@router.patch("/chat/groups/{conversation_id}/members/ban")
async def ban_member(
    request: Request,
    session: DbSession,
    context: GroupAdmin,
    conversation_id: str,
    payload: BanMemberRequest,
    _=Depends(require_csrf),
):
    svc = chat_service(request, session, context)
    await svc.ban_member(conversation_id, payload.user_id)
    return success_response(request, None)


@router.patch("/chat/groups/{conversation_id}/members/unban")
async def unban_member(
    request: Request,
    session: DbSession,
    context: GroupAdmin,
    conversation_id: str,
    payload: BanMemberRequest,
    _=Depends(require_csrf),
):
    svc = chat_service(request, session, context)
    await svc.unban_member(conversation_id, payload.user_id)
    return success_response(request, None)


# =============================================================================
# Announcements
# =============================================================================


@router.post("/chat/groups/{conversation_id}/announcements", status_code=201)
async def create_announcement(
    request: Request,
    session: DbSession,
    context: GroupAdmin,
    conversation_id: str,
    payload: GroupAnnouncementCreate,
    _=Depends(require_csrf),
):
    svc = chat_service(request, session, context)
    return success_response(
        request,
        await svc.create_announcement(conversation_id, payload.title, payload.content),
        status_code=201,
    )


@router.get("/chat/groups/{conversation_id}/announcements")
async def list_announcements(
    request: Request,
    session: DbSession,
    context: GroupAdmin,
    conversation_id: str,
):
    svc = chat_service(request, session, context)
    return success_response(request, await svc.list_announcements(conversation_id))


# =============================================================================
# File management (admin)
# =============================================================================


@router.get("/files")
async def list_files(
    request: Request,
    session: DbSession,
    context: FileViewer,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    mime_type: str | None = Query(default=None),
):
    svc = file_service(request, session, context)
    data, total = await svc.list_files(page, page_size, mime_type)
    return success_response(request, data, page=page, page_size=page_size, total=total)


@router.get("/files/{file_id}")
async def get_file_detail(
    request: Request,
    session: DbSession,
    context: FileViewer,
    file_id: str,
):
    svc = file_service(request, session, context)
    return success_response(request, await svc.get_file_metadata(file_id))


@router.delete("/files/{file_id}")
async def delete_file(
    request: Request,
    session: DbSession,
    context: FileManager,
    file_id: str,
    _=Depends(require_csrf),
):
    svc = file_service(request, session, context)
    await svc.delete_file(file_id)
    return success_response(request, None)


@router.get("/files/stats")
async def file_stats(
    request: Request,
    session: DbSession,
    context: FileViewer,
):
    svc = file_service(request, session, context)
    return success_response(request, await svc.storage_stats())
