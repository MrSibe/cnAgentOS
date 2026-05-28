from functools import lru_cache

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    app_name: str = "cnAgentOS"
    environment: str = Field(default="development", validation_alias="APP_ENV")
    database_url: str = Field(
        validation_alias=AliasChoices("DATABASE_URL", "CNAGENTOS_DATABASE_URL")
    )
    csrf_secret: str = Field(
        default="development-only-change-me",
        validation_alias="CSRF_SECRET",
        min_length=16,
    )
    encryption_key: str = Field(
        default="dev-only-32-byte-key-for-testing",
        validation_alias="ENCRYPTION_KEY",
        min_length=32,
    )
    session_hours: int = Field(
        default=8, validation_alias="SESSION_HOURS", gt=0, le=720
    )
    cookie_secure: bool = Field(default=False, validation_alias="COOKIE_SECURE")

    @property
    def session_cookie_name(self) -> str:
        if self.environment.lower() == "production":
            return "__Host-cnagentos_session"
        return "cnagentos_session"

    @property
    def use_secure_cookie(self) -> bool:
        return self.environment.lower() == "production" or self.cookie_secure

    @model_validator(mode="after")
    def production_must_set_secrets(self):
        if self.environment.lower() == "production":
            if self.csrf_secret == "development-only-change-me":
                raise ValueError("production requires an explicit CSRF_SECRET")
            if self.encryption_key == "dev-only-32-byte-key-for-testing":
                raise ValueError("production requires an explicit ENCRYPTION_KEY")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
