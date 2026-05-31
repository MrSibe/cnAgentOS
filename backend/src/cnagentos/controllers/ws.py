"""WebSocket endpoint for real-time chat (Phase 6).

Protocol (matching ``docs/api/ws-chat.md``):
  - Authenticate via session cookie on upgrade.
  - JSON message frames: ``{"type": "<event>", "payload": {...}, "id": "<opt>"}``
  - Server pushes: ``connected``, ``new_message``, ``message_read``,
    ``friend_request``, ``typing``, ``presence``, ``error``.
  - Client sends: ``send_message``, ``mark_read``, ``typing``, ``ping``.
  - Heartbeat: server pings every 30s (TBD — rely on client ping for now).
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from cnagentos.api import ApiError
from cnagentos.config import get_settings
from cnagentos.services.auth import load_context
from cnagentos.services.chat import ChatService
from cnagentos.services.ws_manager import (
    broadcast_presence,
    broadcast_to_conversation,
    register,
    unregister,
)

router = APIRouter()


@router.websocket("/api/v1/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()

    settings = get_settings()
    session_token = websocket.cookies.get(settings.session_cookie_name)

    if not session_token:
        await websocket.send_json(
            {"type": "error", "payload": {"code": "UNAUTHENTICATED"}}
        )
        await websocket.close(code=4001)
        return

    sessionmaker = websocket.app.state.sessionmaker
    try:
        async with sessionmaker() as db_session:
            context = await load_context(db_session, settings, session_token)
    except ApiError:
        await websocket.send_json(
            {"type": "error", "payload": {"code": "UNAUTHENTICATED"}}
        )
        await websocket.close(code=4001)
        return

    user_id = context.user.id
    register(user_id, websocket)
    await broadcast_presence(user_id, "online")

    await websocket.send_json(
        {
            "type": "connected",
            "payload": {
                "user_id": user_id,
                "username": context.user.username,
            },
        }
    )

    ip_address = websocket.client.host if websocket.client else None

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "")
            payload = data.get("payload", {})
            msg_id = data.get("id")

            try:
                if msg_type == "send_message":
                    conv_id = payload.get("conversation_id")
                    content = payload.get("content", "")
                    reply_to = payload.get("reply_to_id")
                    async with sessionmaker() as db_session:
                        service = ChatService(
                            db_session, actor=context.user, ip_address=ip_address
                        )
                        message = await service.send_message(
                            conv_id, "text", content, reply_to
                        )
                    # Send confirmation back to sender
                    await websocket.send_json(
                        {"type": "new_message", "payload": message, "id": msg_id}
                    )
                    # Broadcast to other conversation members
                    member_ids = await _get_member_ids(sessionmaker, conv_id)
                    await broadcast_to_conversation(
                        member_ids,
                        {"type": "new_message", "payload": message},
                        exclude_user_id=user_id,
                    )

                elif msg_type == "mark_read":
                    conv_id = payload.get("conversation_id")
                    last_read = payload.get("last_read_message_id")
                    async with sessionmaker() as db_session:
                        service = ChatService(
                            db_session, actor=context.user, ip_address=ip_address
                        )
                        await service.mark_read(conv_id, last_read)
                    # Notify conversation members about read status
                    member_ids = await _get_member_ids(sessionmaker, conv_id)
                    await broadcast_to_conversation(
                        member_ids,
                        {
                            "type": "message_read",
                            "payload": {
                                "conversation_id": conv_id,
                                "message_id": last_read,
                                "user_id": user_id,
                            },
                        },
                        exclude_user_id=user_id,
                    )

                elif msg_type == "typing":
                    conv_id = payload.get("conversation_id")
                    is_typing = payload.get("is_typing", True)
                    member_ids = await _get_member_ids(sessionmaker, conv_id)
                    await broadcast_to_conversation(
                        member_ids,
                        {
                            "type": "typing",
                            "payload": {
                                "conversation_id": conv_id,
                                "user_id": user_id,
                                "is_typing": is_typing,
                            },
                        },
                        exclude_user_id=user_id,
                    )

                elif msg_type == "ping":
                    await websocket.send_json(
                        {"type": "pong", "id": msg_id}
                    )

                else:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "payload": {"code": "UNKNOWN_TYPE", "message": f"未知消息类型: {msg_type}"},
                            "id": msg_id,
                        }
                    )

            except ApiError as e:
                await websocket.send_json(
                    {
                        "type": "error",
                        "payload": {"code": e.code, "message": e.message},
                        "id": msg_id,
                    }
                )

    except WebSocketDisconnect:
        pass
    except Exception:
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
    finally:
        unregister(user_id, websocket)
        # Broadcast offline status (ws_manager tracks remaining connections)
        await broadcast_presence(user_id, "offline")


async def _get_member_ids(sessionmaker, conversation_id: str) -> list[str]:
    """Return the list of user IDs that are members of *conversation_id*."""
    from sqlalchemy import select
    from cnagentos.models.entities import ConversationMember

    async with sessionmaker() as db_session:
        rows = (
            await db_session.scalars(
                select(ConversationMember.user_id).where(
                    ConversationMember.conversation_id == conversation_id
                )
            )
        ).all()
        return list(rows)
