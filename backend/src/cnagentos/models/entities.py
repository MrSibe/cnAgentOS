from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cnagentos.db import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


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

    __table_args__ = (
        Index(
            "ix_model_configs_is_default",
            is_default,
            unique=True,
            postgresql_where=is_default.is_(True),
        ),
    )


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
