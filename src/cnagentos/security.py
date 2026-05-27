import asyncio
import hashlib
import hmac
import secrets
from functools import lru_cache

from pwdlib import PasswordHash

from cnagentos.api import ApiError


PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 128
password_hasher = PasswordHash.recommended()


@lru_cache(maxsize=1)
def _get_dummy_password_hash() -> str:
    return password_hasher.hash("dummy-password-not-used")


def validate_password(password: str) -> None:
    if not PASSWORD_MIN_LENGTH <= len(password) <= PASSWORD_MAX_LENGTH:
        raise ApiError(
            400,
            "VALIDATION_ERROR",
            "请求参数无效",
            {"password": "密码长度必须在 12 到 128 个字符之间"},
        )


def hash_password(password: str) -> str:
    validate_password(password)
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    return password_hasher.verify(password, password_hash or _get_dummy_password_hash())


async def verify_password_async(password: str, password_hash: str | None) -> bool:
    return await asyncio.to_thread(verify_password, password, password_hash)


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def csrf_token_for_session(session_token: str, secret: str) -> str:
    return hmac.new(
        secret.encode("utf-8"), session_token.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def tokens_match(left: str | None, right: str) -> bool:
    return bool(left) and hmac.compare_digest(left, right)
