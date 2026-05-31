from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cnagentos.db import Base


def utc_now() -> datetime:
    """Return current UTC time as a naive datetime for cross-DB compatibility.

    SQLite does not support timezone-aware storage, while PostgreSQL does.
    Using naive UTC everywhere avoids ``TypeError: can't compare offset-naive
    and offset-aware datetimes`` when switching between databases.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="active")
    is_system_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    role_links: Mapped[list["UserRole"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    csrf_secret_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user: Mapped[User] = relationship()


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    permission_links: Mapped[list["RolePermission"]] = relationship(
        back_populates="role", cascade="all, delete-orphan"
    )


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    module: Mapped[str] = mapped_column(String(80))
    function_id: Mapped[str | None] = mapped_column(
        ForeignKey("functions.id"), nullable=True
    )
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Function(Base):
    __tablename__ = "functions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    parent_id: Mapped[str | None] = mapped_column(
        ForeignKey("functions.id"), nullable=True, index=True
    )
    route_path: Mapped[str | None] = mapped_column(String(255))
    icon: Mapped[str | None] = mapped_column(String(80))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    required_permission_code: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="disabled")
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    role_id: Mapped[str] = mapped_column(ForeignKey("roles.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    user: Mapped[User] = relationship(back_populates="role_links")
    role: Mapped[Role] = relationship()


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id: Mapped[str] = mapped_column(ForeignKey("roles.id"), primary_key=True)
    permission_id: Mapped[str] = mapped_column(
        ForeignKey("permissions.id"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    role: Mapped[Role] = relationship(back_populates="permission_links")
    permission: Mapped[Permission] = relationship()


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    actor_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(100), index=True)
    target_type: Mapped[str] = mapped_column(String(80), index=True)
    target_id: Mapped[str | None] = mapped_column(String(36))
    result: Mapped[str] = mapped_column(String(20))
    detail: Mapped[dict | None] = mapped_column(JSON)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )

    actor: Mapped[User | None] = relationship()


class ModelConfig(Base):
    __tablename__ = "model_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    provider_type: Mapped[str] = mapped_column(String(40), default="openai_compatible")
    model_name: Mapped[str] = mapped_column(String(120))
    base_url: Mapped[str] = mapped_column(String(512))
    credential_ciphertext: Mapped[str] = mapped_column(Text)
    credential_mask: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), default="disabled")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=60)
    description: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    creator: Mapped[User | None] = relationship()

    # Note: is_default uniqueness is enforced at the application layer
    # (ModelEngineService.set_default_model clears existing default in a
    # single transaction before setting the new one). The PostgreSQL-specific
    # partial unique index was removed in Phase 5 for SQLite compatibility.


class ModelCallLog(Base):
    __tablename__ = "model_call_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    model_config_id: Mapped[str | None] = mapped_column(
        ForeignKey("model_configs.id"), nullable=True, index=True
    )
    caller_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    purpose: Mapped[str] = mapped_column(String(40))
    related_id: Mapped[str | None] = mapped_column(String(36))
    streamed: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="running")
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    total_tokens: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(40))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    model_config: Mapped[ModelConfig | None] = relationship()
    caller: Mapped[User | None] = relationship()


class WatchSource(Base):
    __tablename__ = "watch_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    source_type: Mapped[str] = mapped_column(String(20))
    entry_url: Mapped[str] = mapped_column(String(2048))
    allowed_hosts: Mapped[list] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="disabled")
    auth_ciphertext: Mapped[str | None] = mapped_column(Text)
    auth_mask: Mapped[str | None] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    creator: Mapped[User | None] = relationship()
    rules: Mapped[list["WatchRule"]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )


class WatchRule(Base):
    __tablename__ = "watch_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("watch_sources.id"))
    name: Mapped[str] = mapped_column(String(120))
    request_method: Mapped[str] = mapped_column(String(10))
    request_headers: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    request_params: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    extractor_type: Mapped[str] = mapped_column(String(20))
    extractor_config: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="disabled")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    source: Mapped[WatchSource] = relationship(back_populates="rules")


class CollectionTask(Base):
    __tablename__ = "collection_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    trigger_type: Mapped[str] = mapped_column(String(20), default="manual")
    source_count: Mapped[int] = mapped_column(Integer, default=0)
    item_success_count: Mapped[int] = mapped_column(Integer, default=0)
    item_failure_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_summary: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    creator: Mapped[User | None] = relationship()
    task_sources: Mapped[list["CollectionTaskSource"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )
    knowledge_items: Mapped[list["CollectionTaskItem"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )


class CollectionTaskSource(Base):
    __tablename__ = "collection_task_sources"

    task_id: Mapped[str] = mapped_column(ForeignKey("collection_tasks.id"), primary_key=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("watch_sources.id"), primary_key=True)
    rule_id: Mapped[str] = mapped_column(ForeignKey("watch_rules.id"))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    failure_summary: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    task: Mapped[CollectionTask] = relationship(back_populates="task_sources")
    source: Mapped[WatchSource] = relationship()
    rule: Mapped[WatchRule] = relationship()


class KnowledgeItem(Base):
    __tablename__ = "knowledge_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_id: Mapped[str | None] = mapped_column(ForeignKey("watch_sources.id"), nullable=True)
    task_id: Mapped[str | None] = mapped_column(ForeignKey("collection_tasks.id"), nullable=True)
    external_key: Mapped[str | None] = mapped_column(String(512))
    canonical_url: Mapped[str | None] = mapped_column(String(2048))
    title: Mapped[str | None] = mapped_column(String(512))
    content: Mapped[str] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    content_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="available")
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    source: Mapped[WatchSource | None] = relationship()
    task: Mapped[CollectionTask | None] = relationship()
    reviewer: Mapped[User | None] = relationship()
    task_items: Mapped[list["CollectionTaskItem"]] = relationship(
        back_populates="knowledge_item", cascade="all, delete-orphan"
    )


class CollectionTaskItem(Base):
    __tablename__ = "collection_task_items"

    task_id: Mapped[str] = mapped_column(ForeignKey("collection_tasks.id"), primary_key=True)
    knowledge_item_id: Mapped[str] = mapped_column(ForeignKey("knowledge_items.id"), primary_key=True)
    source_id: Mapped[str | None] = mapped_column(ForeignKey("watch_sources.id"), nullable=True)
    ingest_result: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    task: Mapped[CollectionTask] = relationship(back_populates="knowledge_items")
    knowledge_item: Mapped[KnowledgeItem] = relationship(back_populates="task_items")
    source: Mapped[WatchSource | None] = relationship()


# =============================================================================
# 智能问数 (Question Answering)
# =============================================================================

class QaSession(Base):
    __tablename__ = "qa_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    user: Mapped[User] = relationship()
    messages: Mapped[list["QaMessage"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_qa_sessions_user_updated", "user_id", "updated_at"),)


class QaMessage(Base):
    __tablename__ = "qa_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("qa_sessions.id"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    reply_to_id: Mapped[str | None] = mapped_column(ForeignKey("qa_messages.id"), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="completed")
    model_call_log_id: Mapped[str | None] = mapped_column(
        ForeignKey("model_call_logs.id"), nullable=True
    )
    error_summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    session: Mapped[QaSession] = relationship(back_populates="messages")
    reply_to: Mapped["QaMessage | None"] = relationship(remote_side=[id])
    model_call_log: Mapped[ModelCallLog | None] = relationship()
    citations: Mapped[list["QaCitation"]] = relationship(
        back_populates="answer_message", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_qa_messages_session_created", "session_id", "created_at"),)


class QaCitation(Base):
    __tablename__ = "qa_citations"

    answer_message_id: Mapped[str] = mapped_column(
        ForeignKey("qa_messages.id"), primary_key=True
    )
    knowledge_item_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_items.id"), primary_key=True
    )
    rank: Mapped[int] = mapped_column(Integer)
    excerpt: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    answer_message: Mapped[QaMessage] = relationship(back_populates="citations")
    knowledge_item: Mapped[KnowledgeItem] = relationship()


# =============================================================================
# Phase 6 — 即时通信
# =============================================================================


class Contact(Base):
    __tablename__ = "contacts"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    contact_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    remark: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    user: Mapped[User] = relationship(foreign_keys=[user_id])
    contact: Mapped[User] = relationship(foreign_keys=[contact_id])

    __table_args__ = (
        Index("ix_contacts_user_id", "user_id"),
        Index("ix_contacts_contact_id", "contact_id"),
    )


class FriendRequest(Base):
    __tablename__ = "friend_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    from_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    to_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    message: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now,
    )

    from_user: Mapped[User] = relationship(foreign_keys=[from_user_id])
    to_user: Mapped[User] = relationship(foreign_keys=[to_user_id])

    __table_args__ = (
        Index("ix_friend_requests_from", "from_user_id", "status"),
        Index("ix_friend_requests_to", "to_user_id", "status"),
    )


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    type: Mapped[str] = mapped_column(String(20))
    name: Mapped[str | None] = mapped_column(String(255))
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    is_disbanded: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now,
    )

    creator: Mapped[User] = relationship()
    members: Mapped[list["ConversationMember"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan",
    )
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan",
    )

    __table_args__ = (Index("ix_conversations_created_by", "created_by"),)


class ConversationMember(Base):
    __tablename__ = "conversation_members"

    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id"), primary_key=True,
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(20), default="member")
    last_read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    banned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    banned_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    conversation: Mapped[Conversation] = relationship(back_populates="members")
    user: Mapped[User] = relationship(foreign_keys=[user_id])
    banner: Mapped[User | None] = relationship(foreign_keys=[banned_by])

    __table_args__ = (
        Index("ix_conv_members_conv", "conversation_id"),
        Index("ix_conv_members_user", "user_id"),
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"))
    sender_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    content_type: Mapped[str] = mapped_column(String(20), default="text")
    content: Mapped[str] = mapped_column(Text)
    reply_to_id: Mapped[str | None] = mapped_column(ForeignKey("messages.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now,
    )

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
    sender: Mapped[User] = relationship()
    reply_to: Mapped["Message | None"] = relationship(remote_side=[id])

    __table_args__ = (
        Index("ix_messages_conversation_created", "conversation_id", "created_at"),
        Index("ix_messages_sender", "sender_id"),
    )


class MessageReadReceipt(Base):
    __tablename__ = "message_read_receipts"

    message_id: Mapped[str] = mapped_column(ForeignKey("messages.id"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    __table_args__ = (Index("ix_read_receipts_user", "user_id"),)


class FileBlob(Base):
    __tablename__ = "file_blobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    sha256: Mapped[str] = mapped_column(String(64), unique=True)
    mime_type: Mapped[str] = mapped_column(String(127))
    size_bytes: Mapped[int] = mapped_column(Integer)
    storage_path: Mapped[str] = mapped_column(String(1024))
    ref_count: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class File(Base):
    __tablename__ = "files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    blob_id: Mapped[str] = mapped_column(ForeignKey("file_blobs.id"))
    filename: Mapped[str] = mapped_column(String(255))
    uploaded_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    blob: Mapped[FileBlob] = relationship()
    uploader: Mapped[User] = relationship()

    __table_args__ = (Index("ix_files_uploaded_by", "uploaded_by"),)


# =============================================================================
# Phase 7 — 数字员工、工具、服务器与群增强
# =============================================================================


class DigitalEmployee(Base):
    __tablename__ = "digital_employees"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    code: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    avatar: Mapped[str | None] = mapped_column(String(512))
    description: Mapped[str | None] = mapped_column(Text)
    system_prompt: Mapped[str] = mapped_column(Text)
    model_config_id: Mapped[str | None] = mapped_column(
        ForeignKey("model_configs.id"), nullable=True,
    )
    trigger_type: Mapped[str] = mapped_column(String(20), default="mention")
    max_turns: Mapped[int] = mapped_column(Integer, default=20)
    status: Mapped[str] = mapped_column(String(20), default="disabled")
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now,
    )

    model_config: Mapped[ModelConfig | None] = relationship()
    creator: Mapped[User | None] = relationship()
    tool_bindings: Mapped[list["EmployeeToolBinding"]] = relationship(
        back_populates="employee", cascade="all, delete-orphan",
    )


class Tool(Base):
    __tablename__ = "tools"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    code: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    tool_type: Mapped[str] = mapped_column(String(30))
    config: Mapped[dict] = mapped_column(JSON)
    config_ciphertext: Mapped[str | None] = mapped_column(Text)
    config_mask: Mapped[str | None] = mapped_column(String(120))
    invocation_limit: Mapped[int] = mapped_column(Integer, default=100)
    invocation_window_seconds: Mapped[int] = mapped_column(Integer, default=3600)
    status: Mapped[str] = mapped_column(String(20), default="disabled")
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now,
    )

    creator: Mapped[User | None] = relationship()
    employee_bindings: Mapped[list["EmployeeToolBinding"]] = relationship(
        back_populates="tool", cascade="all, delete-orphan",
    )


class EmployeeToolBinding(Base):
    __tablename__ = "employee_tool_bindings"

    employee_id: Mapped[str] = mapped_column(
        ForeignKey("digital_employees.id"), primary_key=True,
    )
    tool_id: Mapped[str] = mapped_column(
        ForeignKey("tools.id"), primary_key=True,
    )
    binding_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    employee: Mapped[DigitalEmployee] = relationship(back_populates="tool_bindings")
    tool: Mapped[Tool] = relationship(back_populates="employee_bindings")


class ToolInvocationLog(Base):
    __tablename__ = "tool_invocation_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tool_id: Mapped[str] = mapped_column(ForeignKey("tools.id"), index=True)
    employee_id: Mapped[str | None] = mapped_column(
        ForeignKey("digital_employees.id"), nullable=True,
    )
    message_id: Mapped[str | None] = mapped_column(ForeignKey("messages.id"), nullable=True)
    caller_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    input_params: Mapped[dict | None] = mapped_column(JSON)
    output_summary: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20))
    error_code: Mapped[str | None] = mapped_column(String(40))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    tool: Mapped[Tool] = relationship()
    employee: Mapped[DigitalEmployee | None] = relationship()
    caller: Mapped[User | None] = relationship()

    __table_args__ = (
        Index("ix_tool_invocation_tool", "tool_id", "created_at"),
        Index("ix_tool_invocation_employee", "employee_id", "created_at"),
    )


class ChatServer(Base):
    __tablename__ = "chat_servers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    base_url: Mapped[str] = mapped_column(String(512))
    health_check_url: Mapped[str | None] = mapped_column(String(512))
    auth_ciphertext: Mapped[str | None] = mapped_column(Text)
    auth_mask: Mapped[str | None] = mapped_column(String(120))
    priority: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="disabled")
    last_health_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_health_check_result: Mapped[str | None] = mapped_column(String(20))
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now,
    )

    creator: Mapped[User | None] = relationship()


class GroupAnnouncement(Base):
    __tablename__ = "group_announcements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    title: Mapped[str | None] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now,
    )

    conversation: Mapped[Conversation] = relationship()
    creator: Mapped[User] = relationship()

    __table_args__ = (
        Index("ix_group_announcements_conv", "conversation_id", "created_at"),
    )


class SentimentTask(Base):
    """舆情分析任务 (Phase 8)"""
    __tablename__ = "sentiment_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    task_type: Mapped[str] = mapped_column(String(40), default="full")
    data_scope: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    include_chat_data: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now,
    )

    creator: Mapped[User] = relationship()
    reports: Mapped[list["SentimentReport"]] = relationship(
        back_populates="task", cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_sentiment_tasks_status", "status", "created_at"),
        Index("ix_sentiment_tasks_creator", "created_by", "created_at"),
    )


class SentimentReport(Base):
    """舆情分析报告 (Phase 8)"""
    __tablename__ = "sentiment_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("sentiment_tasks.id"), index=True)
    report_type: Mapped[str] = mapped_column(String(40))
    report_data: Mapped[dict] = mapped_column(JSON)
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_item_count: Mapped[int] = mapped_column(Integer, default=0)
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    task: Mapped[SentimentTask] = relationship(back_populates="reports")

    __table_args__ = (
        Index("ix_sentiment_reports_task", "task_id", "report_type"),
    )
