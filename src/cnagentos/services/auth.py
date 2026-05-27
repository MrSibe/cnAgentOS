from dataclasses import dataclass
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from cnagentos.api import ApiError
from cnagentos.config import Settings
from cnagentos.models.entities import AuthSession, Permission, Role, RolePermission, User, UserRole, utc_now
from cnagentos.security import (
    csrf_token_for_session,
    hash_token,
    new_session_token,
    verify_password_async,
)


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
        .options(selectinload(AuthSession.user))
        .where(AuthSession.token_hash == hash_token(raw_token))
    )
    now = utc_now()
    if (
        auth_session is None
        or auth_session.revoked_at is not None
        or auth_session.expires_at <= now
        or auth_session.user.status != "active"
    ):
        raise ApiError(401, "AUTH_REQUIRED", "登录状态已失效")

    csrf_token = csrf_token_for_session(raw_token, settings.csrf_secret)
    if auth_session.csrf_secret_hash != hash_token(csrf_token):
        raise ApiError(401, "AUTH_REQUIRED", "登录状态已失效")
    auth_session.last_seen_at = now
    permissions = await get_permission_codes(session, auth_session.user_id)
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
