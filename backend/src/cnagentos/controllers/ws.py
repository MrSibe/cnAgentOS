"""WebSocket endpoint for real-time chat (Phase 6 + Phase 7).

Phase 7 enhancements:
  - ``content_type: "file"`` with file_id validation
  - @mention detection for digital employees
  - ``employee_reply`` and ``employee_typing`` event push
"""

import asyncio
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from cnagentos.api import ApiError
from cnagentos.config import get_settings
from cnagentos.models.entities import Message, utc_now
from cnagentos.services.auth import load_context
from cnagentos.services.bootstrap import SYSTEM_TASK_USER_ID
from cnagentos.services.chat import ChatService
from cnagentos.services.employee import DigitalEmployeeService
from cnagentos.services.file import FileService
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
                    content_type = payload.get("content_type", "text")
                    content = payload.get("content", "")
                    reply_to = payload.get("reply_to_id")

                    async with sessionmaker() as db_session:
                        service = ChatService(
                            db_session, actor=context.user, ip_address=ip_address,
                        )

                        # Validate file_id for file/image messages
                        if content_type in ("file", "image"):
                            file_id = content
                            try:
                                file_service = FileService(db_session, context.user)
                                file_meta = await file_service.get_file_metadata(file_id)
                            except ApiError as e:
                                await websocket.send_json({
                                    "type": "error",
                                    "payload": {"code": "INVALID_FILE", "message": "文件不存在或无权访问"},
                                    "id": msg_id,
                                })
                                continue

                        # Send message
                        message = await service.send_message(
                            conv_id, content_type, content, reply_to,
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

                    # Phase 7: @mention detection for digital employees
                    if content_type == "text":
                        async with sessionmaker() as db_session:
                            emp_svc = DigitalEmployeeService(
                                db_session, actor=context.user, ip_address=ip_address,
                            )
                            mentioned = await emp_svc.detect_mentions(content)

                        for emp in mentioned:
                            # Trigger employee reply asynchronously
                            asyncio.create_task(
                                _trigger_employee_reply(
                                    sessionmaker, emp, conv_id,
                                    content, member_ids, user_id,
                                )
                            )

                elif msg_type == "mark_read":
                    conv_id = payload.get("conversation_id")
                    last_read = payload.get("last_read_message_id")
                    async with sessionmaker() as db_session:
                        service = ChatService(
                            db_session, actor=context.user, ip_address=ip_address,
                        )
                        await service.mark_read(conv_id, last_read)
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
        await broadcast_presence(user_id, "offline")


async def _trigger_employee_reply(
    sessionmaker, employee: dict, conversation_id: str,
    user_message: str, member_ids: list[str], sender_id: str,
) -> None:
    """Asynchronously trigger a digital employee reply in a group chat."""
    # Notify conversation that employee is typing
    await broadcast_to_conversation(
        member_ids,
        {
            "type": "employee_typing",
            "payload": {
                "conversation_id": conversation_id,
                "employee_id": employee["id"],
                "employee_name": employee["name"],
                "is_typing": True,
            },
        },
        exclude_user_id=sender_id,
    )

    try:
        async with sessionmaker() as db_session:
            # Create a system actor context for the employee
            from cnagentos.services.bootstrap import SYSTEM_TASK_USER_ID
            from cnagentos.models.entities import User

            task_user = await db_session.get(User, SYSTEM_TASK_USER_ID)
            if task_user is None:
                return

            emp_svc = DigitalEmployeeService(
                db_session, actor=task_user, ip_address=None,
            )
            result = await emp_svc.invoke_employee(
                employee["id"], conversation_id, user_message,
            )

            # Save the employee reply as a system message
            reply_content = result["reply"]
            msg = Message(
                id=str(uuid4()),
                conversation_id=conversation_id,
                sender_id=SYSTEM_TASK_USER_ID,
                content_type="text",
                content=reply_content,
            )
            db_session.add(msg)
            await db_session.commit()
            await db_session.refresh(msg)

            message_dict = {
                "id": msg.id,
                "conversation_id": msg.conversation_id,
                "sender_id": SYSTEM_TASK_USER_ID,
                "sender_name": employee["name"],
                "content_type": msg.content_type,
                "content": msg.content,
                "reply_to_id": msg.reply_to_id,
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
            }

        # Stop typing indicator
        await broadcast_to_conversation(
            member_ids,
            {
                "type": "employee_typing",
                "payload": {
                    "conversation_id": conversation_id,
                    "employee_id": employee["id"],
                    "employee_name": employee["name"],
                    "is_typing": False,
                },
            },
            exclude_user_id=sender_id,
        )

        # Broadcast the employee reply
        await broadcast_to_conversation(
            member_ids,
            {
                "type": "employee_reply",
                "payload": {
                    "message": message_dict,
                    "employee_id": employee["id"],
                    "employee_name": employee["name"],
                },
            },
        )
    except Exception:
        # Silently handle employee reply failures
        pass


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
