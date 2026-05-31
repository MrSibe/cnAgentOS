from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=128)


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    display_name: str = Field(min_length=1, max_length=120)
    password: str
    role_ids: list[str] = Field(default_factory=list)


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    role_ids: list[str] | None = None

    @model_validator(mode="after")
    def ensure_change(self):
        if self.display_name is None and self.role_ids is None:
            raise ValueError("至少提交一个可修改字段")
        return self


class StatusUpdate(BaseModel):
    status: str


class PasswordReset(BaseModel):
    new_password: str


class RoleCreate(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    permission_ids: list[str] = Field(default_factory=list)


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    status: str | None = None
    permission_ids: list[str] | None = None

    @model_validator(mode="after")
    def ensure_change(self):
        if not self.model_fields_set:
            raise ValueError("至少提交一个可修改字段")
        return self


class FunctionCreate(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=120)
    parent_id: str | None = None
    route_path: str | None = Field(default=None, max_length=255)
    icon: str | None = Field(default=None, max_length=80)
    sort_order: int = 0
    required_permission_code: str | None = None


class FunctionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    parent_id: str | None = None
    route_path: str | None = Field(default=None, max_length=255)
    icon: str | None = Field(default=None, max_length=80)
    sort_order: int | None = None
    required_permission_code: str | None = None
    status: str | None = None

    @model_validator(mode="after")
    def ensure_change(self):
        if not self.model_fields_set:
            raise ValueError("至少提交一个可修改字段")
        return self


class PageParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class AuditFilters(PageParams):
    actor_user_id: str | None = None
    action: str | None = None
    target_type: str | None = None
    target_id: str | None = None
    result: str | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None


class ModelConfigCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    provider_type: str = Field(default="openai_compatible", max_length=40)
    model_name: str = Field(min_length=1, max_length=120)
    base_url: str = Field(min_length=1, max_length=512)
    api_key: str = Field(min_length=1)
    timeout_seconds: int = Field(default=60, gt=0, le=300)
    description: str | None = None


class ModelConfigUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    model_name: str | None = Field(default=None, min_length=1, max_length=120)
    base_url: str | None = Field(default=None, min_length=1, max_length=512)
    api_key: str | None = Field(default=None, min_length=1)
    timeout_seconds: int | None = Field(default=None, gt=0, le=300)
    description: str | None = None


class ConnectionTestRequest(BaseModel):
    message: str = Field(default="请回复连接正常", min_length=1, max_length=1000)
    stream: bool = False


class ModelCallFilters(PageParams):
    model_id: str | None = None
    purpose: str | None = None
    status: str | None = None
    started_from: datetime | None = None
    started_to: datetime | None = None


# --- Watch Sources ---
class WatchSourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    source_type: str = Field(default="web_page", max_length=20)
    entry_url: str = Field(min_length=1, max_length=2048)
    allowed_hosts: list[str] = Field(min_length=1)
    auth_config: dict | None = None
    description: str | None = None


class WatchSourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    entry_url: str | None = Field(default=None, min_length=1, max_length=2048)
    allowed_hosts: list[str] | None = None
    auth_config: dict | None = None
    description: str | None = None

    @model_validator(mode="after")
    def ensure_change(self):
        if self.name is None and self.entry_url is None and self.allowed_hosts is None and self.auth_config is None and self.description is None:
            raise ValueError("至少提交一个可修改字段")
        return self


# --- Watch Rules ---
class WatchRuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    request_method: str = Field(default="GET", max_length=10)
    request_headers: dict | None = None
    request_params: dict | None = None
    extractor_type: str = Field(default="html", max_length=20)
    extractor_config: dict = Field(min_length=1)


class WatchRuleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    request_method: str | None = Field(default=None, max_length=10)
    request_headers: dict | None = None
    request_params: dict | None = None
    extractor_type: str | None = Field(default=None, max_length=20)
    extractor_config: dict | None = None
    status: str | None = None

    @model_validator(mode="after")
    def ensure_change(self):
        if self.name is None and self.request_method is None and self.request_headers is None and self.request_params is None and self.extractor_type is None and self.extractor_config is None and self.status is None:
            raise ValueError("至少提交一个可修改字段")
        return self


# --- Collection Tasks ---
class CollectionTaskTarget(BaseModel):
    source_id: str
    rule_id: str
    variables: dict | None = None


class CollectionTaskCreate(BaseModel):
    targets: list[CollectionTaskTarget] = Field(min_length=1)


# --- Knowledge Items ---
class KnowledgeItemFilters(PageParams):
    source_id: str | None = None
    status: str | None = None
    collected_from: datetime | None = None
    collected_to: datetime | None = None


# =============================================================================
# 智能问数 (Question Answering)
# =============================================================================

class QASessionCreate(BaseModel):
    title: str | None = Field(default=None, max_length=256)


class QASessionUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=256)
    status: str | None = None

    @model_validator(mode="after")
    def ensure_change(self):
        if self.title is None and self.status is None:
            raise ValueError("至少提交一个可修改字段")
        return self


class QASessionFilters(PageParams):
    q: str | None = None


class QAQuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class QACitationSummary(BaseModel):
    knowledge_item_id: str
    rank: int
    title: str | None = None
    source_name: str | None = None
    excerpt: str
    current_status: str | None = None


class QAMessageSummary(BaseModel):
    id: str
    role: str
    content: str
    status: str
    created_at: datetime
    citations: list[QACitationSummary] = Field(default_factory=list)


# =============================================================================
# User Registration (Phase 6+)
# =============================================================================

class RegisterRequest(BaseModel):
    """Self-registration for new users. Endpoint implemented in Phase 6."""
    username: str = Field(
        min_length=4, max_length=30,
        pattern=r"^[a-zA-Z][a-zA-Z0-9_-]{2,28}[a-zA-Z0-9]$",
    )
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=12, max_length=128)


class RegisterResponse(BaseModel):
    id: str
    username: str
    display_name: str


# =============================================================================
# 即时通信 (Chat, Phase 6)
# =============================================================================


class FriendRequestSend(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    message: str | None = Field(default=None, max_length=500)


class FriendRequestAction(BaseModel):
    action: str = Field(pattern=r"^(accept|reject)$")


class ConversationCreate(BaseModel):
    member_usernames: list[str] = Field(min_length=1, max_length=200)
    name: str | None = Field(default=None, max_length=255)


class MessageSend(BaseModel):
    conversation_id: str
    content_type: str = Field(default="text", pattern=r"^(text|system|file|image)$")
    content: str = Field(min_length=1, max_length=5000)
    reply_to_id: str | None = None


class MarkReadRequest(BaseModel):
    conversation_id: str
    last_read_message_id: str


# =============================================================================
# Phase 7 — 数字员工、工具、服务器与群增强
# =============================================================================


class DigitalEmployeeCreate(BaseModel):
    code: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=1, max_length=120)
    avatar: str | None = Field(default=None, max_length=512)
    description: str | None = None
    system_prompt: str = Field(min_length=1)
    model_config_id: str | None = None
    trigger_type: str = Field(default="mention", pattern=r"^(mention|direct_chat)$")
    max_turns: int = Field(default=20, ge=1, le=100)


class DigitalEmployeeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    avatar: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    model_config_id: str | None = None
    trigger_type: str | None = Field(default=None, pattern=r"^(mention|direct_chat)$")
    max_turns: int | None = Field(default=None, ge=1, le=100)


class ToolCreate(BaseModel):
    code: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    tool_type: str = Field(pattern=r"^(api_call|builtin_function|web_search)$")
    config: dict = Field(min_length=1)
    sensitive_config: str | None = None
    invocation_limit: int = Field(default=100, ge=1)
    invocation_window_seconds: int = Field(default=3600, ge=1)


class ToolUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    config: dict | None = None
    sensitive_config: str | None = None
    invocation_limit: int | None = Field(default=None, ge=1)
    invocation_window_seconds: int | None = Field(default=None, ge=1)


class ToolBindRequest(BaseModel):
    tool_id: str
    binding_config: dict | None = None


class ChatServerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    base_url: str = Field(min_length=1, max_length=512)
    health_check_url: str | None = Field(default=None, max_length=512)
    auth_token: str | None = None
    priority: int = Field(default=0)


class ChatServerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    base_url: str | None = Field(default=None, min_length=1, max_length=512)
    health_check_url: str | None = None
    auth_token: str | None = None
    priority: int | None = None


class GroupAnnouncementCreate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    content: str = Field(min_length=1)


class BanMemberRequest(BaseModel):
    user_id: str
