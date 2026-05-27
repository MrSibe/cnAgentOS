from fastapi import APIRouter, Depends, Request, Response

from cnagentos.api import success_response
from cnagentos.controllers.dependencies import AppSettings, CurrentContext, DbSession, require_csrf
from cnagentos.schemas import LoginRequest
from cnagentos.services import auth as auth_service
from cnagentos.services.platform import PlatformService


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login")
async def login(
    payload: LoginRequest, request: Request, session: DbSession, settings: AppSettings
):
    user, session_token, csrf_token = await auth_service.login(
        session,
        settings,
        payload.username,
        payload.password,
        request.client.host if request.client else None,
        request.headers.get("user-agent"),
    )
    response = success_response(
        request,
        {
            "user": {
                "id": user.id,
                "username": user.username,
                "display_name": user.display_name,
            },
            "csrf_token": csrf_token,
        },
    )
    response.set_cookie(
        settings.session_cookie_name,
        session_token,
        max_age=settings.session_hours * 3600,
        httponly=True,
        secure=settings.use_secure_cookie,
        samesite="lax",
        path="/",
    )
    return response


@router.post("/logout", status_code=204, dependencies=[Depends(require_csrf)])
async def logout(
    request: Request,
    session: DbSession,
    settings: AppSettings,
    context: CurrentContext,
) -> Response:
    await auth_service.logout(session, context)
    response = Response(status_code=204)
    response.delete_cookie(
        settings.session_cookie_name,
        path="/",
        secure=settings.use_secure_cookie,
        httponly=True,
        samesite="lax",
    )
    return response


@router.get("/me")
async def me(request: Request, context: CurrentContext):
    return success_response(
        request,
        {
            "id": context.user.id,
            "username": context.user.username,
            "display_name": context.user.display_name,
            "permissions": sorted(context.permissions),
            "csrf_token": context.csrf_token,
        },
    )


@router.get("/boot")
async def boot(request: Request, session: DbSession, context: CurrentContext):
    service = PlatformService(session, context.user)
    navigation_data = await service.navigation_for(context.permissions)
    return success_response(
        request,
        {
            "user": {
                "id": context.user.id,
                "username": context.user.username,
                "display_name": context.user.display_name,
            },
            "permissions": sorted(context.permissions),
            "csrf_token": context.csrf_token,
            "navigation": navigation_data,
        },
    )


@router.get("/navigation")
async def navigation(request: Request, session: DbSession, context: CurrentContext):
    service = PlatformService(session, context.user)
    return success_response(request, await service.navigation_for(context.permissions))
