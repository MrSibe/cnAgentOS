from collections.abc import Iterable
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cnagentos.api import ApiError
from cnagentos.models.entities import AuditLog, KnowledgeItem, QaMessage, QaSession, User
from cnagentos.services.collection_security import sanitized_url


MAX_QUESTION_LENGTH = 2000

QA_AUDIT_ACTIONS = frozenset(
    {
        "qa.session.created",
        "qa.session.updated",
        "qa.question.submitted",
        "qa.answer.started",
        "qa.answer.completed",
        "qa.answer.failed",
        "qa.citations.viewed",
        "qa.security.rejected",
    }
)

_SENSITIVE_KEYS = {
    "api_key",
    "answer",
    "auth",
    "authorization",
    "content",
    "cookie",
    "credential",
    "credential_ciphertext",
    "headers",
    "internal_prompt",
    "messages",
    "model_prompt",
    "password",
    "prompt",
    "question",
    "request_headers",
    "secret",
    "set-cookie",
    "system_prompt",
    "token",
}


def _not_found(message: str = "资源不存在") -> ApiError:
    return ApiError(404, "NOT_FOUND", message)


def _sanitize_detail(value: Any) -> Any:
    if isinstance(value, dict):
        clean: dict[str, Any] = {}
        for key, nested in value.items():
            key_text = str(key)
            lowered = key_text.lower()
            if lowered in _SENSITIVE_KEYS or any(
                part in lowered for part in ("secret", "token", "password", "prompt")
            ):
                clean[key_text] = "[redacted]"
            elif lowered.endswith("url") or lowered in {"url", "canonical_url"}:
                clean[key_text] = sanitized_url(str(nested))
            else:
                clean[key_text] = _sanitize_detail(nested)
        return clean
    if isinstance(value, list):
        return [_sanitize_detail(item) for item in value]
    if isinstance(value, str) and (
        value.startswith("http://") or value.startswith("https://")
    ):
        return sanitized_url(value)
    return value


async def get_owned_session(
    session: AsyncSession,
    current_user: User,
    session_id: str,
) -> QaSession:
    qa_session = await session.scalar(
        select(QaSession).where(
            QaSession.id == session_id,
            QaSession.user_id == current_user.id,
        )
    )
    if qa_session is None:
        raise _not_found("问数会话不存在")
    return qa_session


async def get_owned_answer_message(
    session: AsyncSession,
    current_user: User,
    answer_message_id: str,
) -> QaMessage:
    message = await session.scalar(
        select(QaMessage)
        .join(QaSession, QaMessage.session_id == QaSession.id)
        .where(
            QaMessage.id == answer_message_id,
            QaMessage.role == "assistant",
            QaSession.user_id == current_user.id,
        )
    )
    if message is None:
        raise _not_found("问数回答不存在")
    return message


def validate_question_text(question: str) -> str:
    normalized = question.strip()
    if not normalized:
        raise ApiError(
            400,
            "VALIDATION_ERROR",
            "请求参数无效",
            {"question": "问题不能为空"},
        )
    if len(normalized) > MAX_QUESTION_LENGTH:
        raise ApiError(
            400,
            "VALIDATION_ERROR",
            "请求参数无效",
            {"question": f"问题长度不能超过 {MAX_QUESTION_LENGTH} 个字符"},
        )
    return normalized


def validate_retrieved_knowledge_items(
    knowledge_items: Iterable[KnowledgeItem],
) -> list[KnowledgeItem]:
    items = list(knowledge_items)
    for item in items:
        if item.status != "available":
            raise ApiError(
                422,
                "QA_CONTEXT_UNSAFE",
                "问数依据未通过安全校验",
                {"knowledge_item_id": item.id, "status": item.status},
            )
    return items


async def write_qa_audit(
    session: AsyncSession,
    actor: User | None,
    action: str,
    target_type: str,
    target_id: str | None,
    result: str,
    detail: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> None:
    if action not in QA_AUDIT_ACTIONS:
        raise ValueError(f"unsupported qa audit action: {action}")
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
