from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from cnagentos.api import ApiError
from cnagentos.config import Settings
from cnagentos.models.entities import (
    AuditLog,
    AuthSession,
    Permission,
    Role,
    RolePermission,
    User,
    UserRole,
    utc_now,
)
from cnagentos.security import csrf_token_for_session, hash_password, hash_token, new_session_token, verify_password_async
from cnagentos.services.bootstrap import DEFAULT_USER_ROLE_CODE


@dataclass
class AuthContext:
    user: User
    auth_session: AuthSession
    permissions: set[str]
    csrf_token: str


async def get_permission_codes(session: AsyncSession, user_id: str) -> set[str]:
    query = (
        select(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(Role, Role.id == RolePermission.role_id)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id, Role.status == "active")
    )
    return set((await session.scalars(query)).all())


async def login(
    session: AsyncSession,
    settings: Settings,
    username: str,
    password: str,
    ip_address: str | None,
    user_agent: str | None,
) -> tuple[User, str, str]:
    user = await session.scalar(select(User).where(User.username == username))
    valid_password = await verify_password_async(password, user.password_hash if user else None)
    if user is None or not valid_password or user.status != "active":
        raise ApiError(401, "LOGIN_FAILED", "用户名或密码错误")

    raw_token = new_session_token()
    csrf_token = csrf_token_for_session(raw_token, settings.csrf_secret)
    auth_session = AuthSession(
        id=str(uuid4()),
        user_id=user.id,
        token_hash=hash_token(raw_token),
        csrf_secret_hash=hash_token(csrf_token),
        expires_at=utc_now() + timedelta(hours=settings.session_hours),
        ip_address=ip_address,
        user_agent=(user_agent or "")[:512] or None,
    )
    user.last_login_at = utc_now()
    session.add(auth_session)
    await session.commit()
    return user, raw_token, csrf_token


async def load_context(
    session: AsyncSession, settings: Settings, raw_token: str | None
) -> AuthContext:
    if not raw_token:
        raise ApiError(401, "AUTH_REQUIRED", "请先登录")
    auth_session = await session.scalar(
        select(AuthSession)
        .options(joinedload(AuthSession.user))
        .where(AuthSession.token_hash == hash_token(raw_token))
    )
    now = utc_now()
    # Normalise DB timestamps that may be timezone-aware (PostgreSQL) or
    # naive (SQLite) so they compare correctly with our naive ``now``.
    expires_at = auth_session.expires_at.replace(tzinfo=None) if auth_session else now
    if (
        auth_session is None
        or auth_session.revoked_at is not None
        or expires_at <= now
        or auth_session.user.status != "active"
    ):
        raise ApiError(401, "AUTH_REQUIRED", "登录状态已失效")

    csrf_token = csrf_token_for_session(raw_token, settings.csrf_secret)
    if auth_session.csrf_secret_hash != hash_token(csrf_token):
        raise ApiError(401, "AUTH_REQUIRED", "登录状态已失效")

    permissions = await get_permission_codes(session, auth_session.user_id)

    last_seen = auth_session.last_seen_at
    if last_seen is not None:
        last_seen = last_seen.replace(tzinfo=None)  # normalise for comparison
    if last_seen is None or (now - last_seen).total_seconds() >= 300:
        auth_session.last_seen_at = now
        await session.commit()
    return AuthContext(auth_session.user, auth_session, permissions, csrf_token)


async def logout(session: AsyncSession, context: AuthContext) -> None:
    context.auth_session.revoked_at = utc_now()
    await session.commit()


async def revoke_user_sessions(session: AsyncSession, user_id: str) -> None:
    active_sessions = (
        await session.scalars(
            select(AuthSession).where(
                AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None)
            )
        )
    ).all()
    now = utc_now()
    for auth_session in active_sessions:
        auth_session.revoked_at = now


# =============================================================================
# Registration (Phase 6)
# =============================================================================


class RegisterRateLimiter:
    """In-memory sliding window rate limiter for user registration.

    Allows up to ``max_attempts`` registrations per IP within a
    ``window_seconds`` period.  Intended as a light deterrent, not a
    production-grade DoS defence.
    """

    def __init__(self, max_attempts: int = 3, window_seconds: int = 3600) -> None:
        self._buckets: dict[str, deque[datetime]] = defaultdict(deque)
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds

    def check(self, ip_address: str) -> bool:
        now = datetime.utcnow()
        bucket = self._buckets[ip_address]
        cutoff = now - timedelta(seconds=self.window_seconds)
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= self.max_attempts:
            return False
        bucket.append(now)
        return True


_register_limiter = RegisterRateLimiter()


async def register_user(
    session: AsyncSession,
    settings: Settings,
    ip_address: str,
    username: str,
    display_name: str,
    password: str,
) -> dict:
    """Create a new self-registered user and assign the default_user role.

    Raises ``ApiError`` for rate-limit, duplicate username, or validation
    failures.
    """
    if not _register_limiter.check(ip_address):
        raise ApiError(429, "RATE_LIMITED", "注册过于频繁，请稍后再试")

    existing = await session.scalar(select(User).where(User.username == username))
    if existing:
        raise ApiError(409, "CONFLICT", "用户名已存在")

    user = User(
        id=str(uuid4()),
        username=username,
        display_name=display_name,
        password_hash=hash_password(password),
        status="active",
        is_system_admin=False,
    )
    session.add(user)
    await session.flush()

    default_role = await session.scalar(
        select(Role).where(Role.code == DEFAULT_USER_ROLE_CODE)
    )
    if default_role:
        session.add(UserRole(user_id=user.id, role_id=default_role.id))

    session.add(
        AuditLog(
            id=str(uuid4()),
            actor_user_id=user.id,
            action="user.registered",
            target_type="user",
            target_id=user.id,
            result="succeeded",
            ip_address=ip_address,
        )
    )
    await session.commit()

    return {"id": user.id, "username": user.username, "display_name": user.display_name}
