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
