from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from cnagentos.api import ApiError
from cnagentos.config import Settings
from cnagentos.db import get_db_session
from cnagentos.security import tokens_match
from cnagentos.services.auth import AuthContext, load_context


DbSession = Annotated[AsyncSession, Depends(get_db_session)]


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


AppSettings = Annotated[Settings, Depends(get_app_settings)]


async def get_current_context(
    request: Request, session: DbSession, settings: AppSettings
) -> AuthContext:
    return await load_context(
        session, settings, request.cookies.get(settings.session_cookie_name)
    )


CurrentContext = Annotated[AuthContext, Depends(get_current_context)]


async def require_csrf(
    context: CurrentContext,
    csrf_header: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> None:
    if not tokens_match(csrf_header, context.csrf_token):
        raise ApiError(403, "CSRF_INVALID", "请求保护校验失败")


def require_permission(code: str):
    async def check_permission(context: CurrentContext) -> AuthContext:
        if code not in context.permissions:
            raise ApiError(403, "PERMISSION_DENIED", "无权执行此操作")
        return context

    return check_permission
