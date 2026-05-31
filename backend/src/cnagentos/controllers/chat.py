"""Chat REST API — contacts, friend requests, conversations, messages."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from cnagentos.api import success_response
from cnagentos.controllers.dependencies import (
    AppSettings,
    CurrentContext,
    DbSession,
    require_csrf,
    require_permission,
)
from cnagentos.schemas import (
    ConversationCreate,
    FriendRequestAction,
    FriendRequestSend,
    MarkReadRequest,
    MessageSend,
)
from cnagentos.services.chat import ChatService

router = APIRouter(prefix="/api/v1/chat", tags=["聊天"])

# Permission-guarded dependency aliases
ChatUser = Annotated[CurrentContext, Depends(require_permission("chat.messages.send"))]
ContactUser = Annotated[CurrentContext, Depends(require_permission("chat.contacts.view"))]
FriendRequestUser = Annotated[CurrentContext, Depends(require_permission("chat.friends.request"))]


def service_for(request: Request, session: DbSession, context: CurrentContext) -> ChatService:
    return ChatService(
        session, context.user, request.client.host if request.client else None,
    )


# =============================================================================
# Contacts
# =============================================================================


@router.get("/contacts")
async def list_contacts(
    request: Request, session: DbSession, context: ContactUser,
):
    svc = service_for(request, session, context)
    return success_response(request, await svc.list_contacts())


@router.get("/users/search")
async def search_users(
    request: Request,
    session: DbSession,
    context: ContactUser,
    q: str = Query(min_length=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    svc = service_for(request, session, context)
    data, total = await svc.search_users(q, page, page_size)
    return success_response(
        request, data, page=page, page_size=page_size, total=total,
    )


# =============================================================================
# Friend requests
# =============================================================================


@router.post("/friend-requests", status_code=201)
async def send_friend_request(
    request: Request,
    session: DbSession,
    context: FriendRequestUser,
    payload: FriendRequestSend,
    _=Depends(require_csrf),
):
    svc = service_for(request, session, context)
    return success_response(
        request, await svc.send_friend_request(payload.username, payload.message),
        status_code=201,
    )


@router.get("/friend-requests/incoming")
async def list_incoming(
    request: Request, session: DbSession, context: FriendRequestUser,
):
    svc = service_for(request, session, context)
    return success_response(request, await svc.list_incoming_requests())


@router.get("/friend-requests/outgoing")
async def list_outgoing(
    request: Request, session: DbSession, context: FriendRequestUser,
):
    svc = service_for(request, session, context)
    return success_response(request, await svc.list_outgoing_requests())


@router.patch("/friend-requests/{request_id}")
async def handle_friend_request(
    request: Request,
    session: DbSession,
    context: FriendRequestUser,
    request_id: str,
    payload: FriendRequestAction,
    _=Depends(require_csrf),
):
    svc = service_for(request, session, context)
    return success_response(
        request, await svc.handle_friend_request(request_id, payload.action),
    )


# =============================================================================
# Conversations
# =============================================================================


@router.get("/conversations")
async def list_conversations(
    request: Request, session: DbSession, context: ChatUser,
):
    svc = service_for(request, session, context)
    return success_response(request, await svc.list_conversations())


@router.post("/conversations", status_code=201)
async def create_group(
    request: Request,
    session: DbSession,
    context: ChatUser,
    payload: ConversationCreate,
    _=Depends(require_csrf),
):
    svc = service_for(request, session, context)
    return success_response(
        request,
        await svc.create_group_conversation(payload.name, payload.member_usernames),
        status_code=201,
    )


@router.get("/conversations/{conversation_id}/members")
async def get_conversation_members(
    request: Request,
    session: DbSession,
    context: ChatUser,
    conversation_id: str,
):
    svc = service_for(request, session, context)
    return success_response(
        request, await svc.get_conversation_members(conversation_id),
    )


@router.post("/conversations/{conversation_id}/leave")
async def leave_group(
    request: Request,
    session: DbSession,
    context: ChatUser,
    conversation_id: str,
    _=Depends(require_csrf),
):
    svc = service_for(request, session, context)
    await svc.leave_group(conversation_id)
    return success_response(request, None)


# =============================================================================
# Messages
# =============================================================================


@router.get("/messages")
async def get_messages(
    request: Request,
    session: DbSession,
    context: ChatUser,
    conversation_id: str = Query(),
    before: str | None = Query(default=None),
    after: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
):
    svc = service_for(request, session, context)
    return success_response(
        request,
        await svc.get_messages(conversation_id, before, after, limit),
    )


@router.post("/messages", status_code=201)
async def send_message(
    request: Request,
    session: DbSession,
    context: ChatUser,
    payload: MessageSend,
    _=Depends(require_csrf),
):
    svc = service_for(request, session, context)
    return success_response(
        request,
        await svc.send_message(
            payload.conversation_id, payload.content_type, payload.content, payload.reply_to_id,
        ),
        status_code=201,
    )


@router.post("/messages/mark-read")
async def mark_read(
    request: Request,
    session: DbSession,
    context: ChatUser,
    payload: MarkReadRequest,
    _=Depends(require_csrf),
):
    svc = service_for(request, session, context)
    await svc.mark_read(payload.conversation_id, payload.last_read_message_id)
    return success_response(request, None)
