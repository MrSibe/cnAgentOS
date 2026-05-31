"""WebSocket connection registry and broadcast helpers for real-time chat.

Maintains a mapping of ``user_id -> list[WebSocket]`` for active
connections and provides helpers to broadcast events to conversation
members or to announce presence changes.
"""

from fastapi import WebSocket

# Module-level registry: user_id -> list of active WebSocket connections
connection_registry: dict[str, list[WebSocket]] = {}


def register(user_id: str, ws: WebSocket) -> None:
    connection_registry.setdefault(user_id, []).append(ws)


def unregister(user_id: str, ws: WebSocket) -> None:
    conns = connection_registry.get(user_id)
    if conns:
        connection_registry[user_id] = [c for c in conns if c is not ws]
        if not connection_registry[user_id]:
            del connection_registry[user_id]


def get_connections(user_id: str) -> list[WebSocket]:
    return connection_registry.get(user_id, [])


async def broadcast_to_users(user_ids: list[str], event: dict) -> None:
    """Send *event* dict as JSON to all online connections of *user_ids*."""
    for uid in user_ids:
        for ws in get_connections(uid):
            try:
                await ws.send_json(event)
            except Exception:
                pass


async def broadcast_to_conversation(
    conversation_member_ids: list[str],
    event: dict,
    exclude_user_id: str | None = None,
) -> None:
    """Broadcast *event* to all online members except *exclude_user_id*."""
    uids = [uid for uid in conversation_member_ids if uid != exclude_user_id]
    await broadcast_to_users(uids, event)


async def broadcast_presence(user_id: str, status: str) -> None:
    """Notify all connected users that *user_id* is now *status*."""
    event = {"type": "presence", "payload": {"user_id": user_id, "status": status}}
    # Broadcast to *all* online users (simple approach for Phase 6)
    for conns in list(connection_registry.values()):
        for ws in conns:
            try:
                await ws.send_json(event)
            except Exception:
                pass
