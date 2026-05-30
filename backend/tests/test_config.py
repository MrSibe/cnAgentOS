import pytest
from pydantic import ValidationError

from cnagentos.config import Settings


def test_production_rejects_default_csrf_secret():
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            APP_ENV="production",
            DATABASE_URL="postgresql+asyncpg://user:pass@127.0.0.1:5432/app",
            CSRF_SECRET="development-only-change-me",
            ENCRYPTION_KEY="production-encryption-key-32-bytes",
        )

    assert "CSRF_SECRET" in str(exc_info.value)


def test_production_rejects_default_encryption_key():
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            APP_ENV="production",
            DATABASE_URL="postgresql+asyncpg://user:pass@127.0.0.1:5432/app",
            CSRF_SECRET="production-csrf-secret-value",
            ENCRYPTION_KEY="dev-only-32-byte-key-for-testing",
        )

    assert "ENCRYPTION_KEY" in str(exc_info.value)


def test_production_uses_host_cookie_and_secure_flag():
    settings = Settings(
        APP_ENV="production",
        DATABASE_URL="postgresql+asyncpg://user:pass@127.0.0.1:5432/app",
        CSRF_SECRET="production-csrf-secret-value",
        ENCRYPTION_KEY="production-encryption-key-32-bytes",
    )

    assert settings.session_cookie_name == "__Host-cnagentos_session"
    assert settings.use_secure_cookie is True
