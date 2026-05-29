from uuid import uuid4

import pytest
from sqlalchemy import select

from cnagentos.api import ApiError
from cnagentos.models.entities import AuditLog, KnowledgeItem, QaMessage, QaSession, User
from cnagentos.services.qa_security import (
    MAX_QUESTION_LENGTH,
    get_owned_answer_message,
    get_owned_session,
    validate_question_text,
    validate_retrieved_knowledge_items,
    write_qa_audit,
)


def make_id(prefix: str) -> str:
    return f"{prefix}-{uuid4()}"[:36]


async def create_user(session, username: str) -> User:
    user = User(
        id=make_id("user"),
        username=username,
        display_name=username,
        password_hash="not-a-real-password-hash",
        status="active",
        is_system_admin=False,
    )
    session.add(user)
    await session.flush()
    return user


async def create_qa_thread(session, user: User) -> tuple[QaSession, QaMessage, QaMessage]:
    qa_session = QaSession(
        id=make_id("qa-session"),
        user_id=user.id,
        title="安全边界测试",
        status="active",
    )
    question = QaMessage(
        id=make_id("question"),
        session_id=qa_session.id,
        role="user",
        content="测试问题",
        status="completed",
    )
    session.add_all([qa_session, question])
    await session.flush()
    answer = QaMessage(
        id=make_id("answer"),
        session_id=qa_session.id,
        role="assistant",
        reply_to_id=question.id,
        content="测试回答",
        status="completed",
    )
    session.add(answer)
    await session.flush()
    return qa_session, question, answer


async def test_owned_session_can_be_loaded(app):
    async with app.state.sessionmaker() as session:
        owner = await create_user(session, f"qa-owner-{uuid4()}")
        qa_session, _, _ = await create_qa_thread(session, owner)
        await session.commit()

        loaded = await get_owned_session(session, owner, qa_session.id)

    assert loaded.id == qa_session.id
    assert loaded.user_id == owner.id


async def test_foreign_and_missing_sessions_share_not_found_boundary(app):
    async with app.state.sessionmaker() as session:
        owner = await create_user(session, f"qa-owner-{uuid4()}")
        intruder = await create_user(session, f"qa-intruder-{uuid4()}")
        qa_session, _, _ = await create_qa_thread(session, owner)
        await session.commit()

        with pytest.raises(ApiError) as foreign_error:
            await get_owned_session(session, intruder, qa_session.id)
        with pytest.raises(ApiError) as missing_error:
            await get_owned_session(session, intruder, make_id("missing-session"))

    assert foreign_error.value.status_code == 404
    assert missing_error.value.status_code == 404
    assert foreign_error.value.code == missing_error.value.code == "NOT_FOUND"
    assert foreign_error.value.message == missing_error.value.message


async def test_owned_answer_message_requires_owner_and_assistant_role(app):
    async with app.state.sessionmaker() as session:
        owner = await create_user(session, f"qa-owner-{uuid4()}")
        intruder = await create_user(session, f"qa-intruder-{uuid4()}")
        _, question, answer = await create_qa_thread(session, owner)
        await session.commit()

        loaded = await get_owned_answer_message(session, owner, answer.id)
        with pytest.raises(ApiError) as user_message_error:
            await get_owned_answer_message(session, owner, question.id)
        with pytest.raises(ApiError) as foreign_answer_error:
            await get_owned_answer_message(session, intruder, answer.id)

    assert loaded.id == answer.id
    assert user_message_error.value.status_code == 404
    assert foreign_answer_error.value.status_code == 404


def test_question_text_is_normalized_and_validated():
    assert validate_question_text("  最近有哪些采集内容？  ") == "最近有哪些采集内容？"

    with pytest.raises(ApiError) as empty_error:
        validate_question_text("  \n\t  ")
    with pytest.raises(ApiError) as long_error:
        validate_question_text("问" * (MAX_QUESTION_LENGTH + 1))

    assert empty_error.value.status_code == 400
    assert long_error.value.status_code == 400
    assert empty_error.value.code == long_error.value.code == "VALIDATION_ERROR"


@pytest.mark.parametrize("status", ["archived", "excluded"])
def test_only_available_knowledge_items_can_be_used_as_qa_context(status):
    item = KnowledgeItem(
        id=make_id("knowledge"),
        title="不可用内容",
        content="这条内容不能作为问数依据",
        content_hash=make_id("hash"),
        status=status,
    )

    with pytest.raises(ApiError) as exc_info:
        validate_retrieved_knowledge_items([item])

    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "QA_CONTEXT_UNSAFE"
    assert exc_info.value.details == {"knowledge_item_id": item.id, "status": status}


def test_available_knowledge_items_are_returned_unchanged():
    item = KnowledgeItem(
        id=make_id("knowledge"),
        title="可用内容",
        content="这条内容可以作为问数依据",
        content_hash=make_id("hash"),
        status="available",
    )

    assert validate_retrieved_knowledge_items([item]) == [item]


async def test_qa_audit_sanitizes_sensitive_detail(app):
    async with app.state.sessionmaker() as session:
        actor = await session.scalar(select(User).where(User.username == "root"))
        target_id = make_id("qa-session")
        await write_qa_audit(
            session,
            actor,
            "qa.security.rejected",
            "qa_session",
            target_id,
            "rejected",
            {
                "url": "https://qa.example.com/path?token=secret",
                "prompt": "internal system prompt",
                "question": "user supplied question",
                "headers": {"Authorization": "Bearer secret"},
                "error_code": "QA_CONTEXT_UNSAFE",
            },
            "127.0.0.1",
        )
        await session.commit()

        log = await session.scalar(
            select(AuditLog).where(
                AuditLog.action == "qa.security.rejected",
                AuditLog.target_id == target_id,
            )
        )

    assert log is not None
    assert log.detail["url"] == "https://qa.example.com/path"
    assert log.detail["prompt"] == "[redacted]"
    assert log.detail["question"] == "[redacted]"
    assert log.detail["headers"] == "[redacted]"
    body = str(log.detail)
    assert "secret" not in body
    assert "Authorization" not in body
    assert "token=" not in body
    assert "internal system prompt" not in body


async def test_qa_audit_rejects_unknown_action_and_result(app):
    async with app.state.sessionmaker() as session:
        actor = await session.scalar(select(User).where(User.username == "root"))

        with pytest.raises(ValueError):
            await write_qa_audit(
                session, actor, "qa.unknown", "qa_session", "id", "succeeded"
            )
        with pytest.raises(ValueError):
            await write_qa_audit(
                session, actor, "qa.security.rejected", "qa_session", "id", "unknown"
            )
