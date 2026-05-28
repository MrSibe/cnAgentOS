from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from cnagentos.models.entities import AuditLog, User
from cnagentos.services.collection_security import sanitized_url


WATCH_AUDIT_ACTIONS = frozenset(
    {
        "watch.source.created",
        "watch.source.updated",
        "watch.source.status_changed",
        "watch.rule.created",
        "watch.rule.updated",
        "watch.task.created",
        "watch.task.cancelled",
        "data.item.status_changed",
    }
)

_SENSITIVE_KEYS = {
    "api_key",
    "auth",
    "auth_config",
    "auth_ciphertext",
    "authorization",
    "cookie",
    "credential",
    "credential_ciphertext",
    "headers",
    "password",
    "request_headers",
    "secret",
    "set-cookie",
    "token",
}


def _sanitize_detail(value: Any) -> Any:
    if isinstance(value, dict):
        clean: dict[str, Any] = {}
        for key, nested in value.items():
            key_text = str(key)
            lowered = key_text.lower()
            if lowered in _SENSITIVE_KEYS or any(part in lowered for part in ("secret", "token", "password")):
                clean[key_text] = "[redacted]"
            elif lowered.endswith("url") or lowered in {"url", "entry_url", "canonical_url"}:
                clean[key_text] = sanitized_url(str(nested))
            else:
                clean[key_text] = _sanitize_detail(nested)
        return clean
    if isinstance(value, list):
        return [_sanitize_detail(item) for item in value]
    if isinstance(value, str) and (value.startswith("http://") or value.startswith("https://")):
        return sanitized_url(value)
    return value


async def write_watch_audit(
    session: AsyncSession,
    actor: User | None,
    action: str,
    target_type: str,
    target_id: str | None,
    result: str,
    detail: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> None:
    if action not in WATCH_AUDIT_ACTIONS:
        raise ValueError(f"unsupported watch audit action: {action}")
    if result not in {"succeeded", "failed", "rejected"}:
        raise ValueError(f"unsupported audit result: {result}")
    session.add(
        AuditLog(
            id=str(uuid4()),
            actor_user_id=actor.id if actor else None,
            action=action,
            target_type=target_type,
            target_id=target_id,
            result=result,
            detail=_sanitize_detail(detail) if detail else None,
            ip_address=ip_address,
        )
    )
