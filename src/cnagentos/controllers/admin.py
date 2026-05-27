from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, Response

from cnagentos.api import ApiError, success_response
from cnagentos.controllers.dependencies import (
    CurrentContext,
    DbSession,
    require_csrf,
    require_permission,
)
from cnagentos.schemas import (
    FunctionCreate,
    FunctionUpdate,
    PasswordReset,
    RoleCreate,
    RoleUpdate,
    StatusUpdate,
    UserCreate,
    UserUpdate,
)
from cnagentos.services.auth import AuthContext
from cnagentos.services.platform import PlatformService


router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
UsersManager = Annotated[AuthContext, Depends(require_permission("users.manage"))]
RolesManager = Annotated[AuthContext, Depends(require_permission("roles.manage"))]
FunctionsManager = Annotated[AuthContext, Depends(require_permission("functions.manage"))]
AuditViewer = Annotated[AuthContext, Depends(require_permission("audit.view"))]


def service_for(request: Request, session: DbSession, context: AuthContext) -> PlatformService:
    return PlatformService(
        session, context.user, request.client.host if request.client else None
    )


async def audit_on_error(
    service: PlatformService,
    action: str,
    target_type: str,
    target_id: str | None,
    operation: Callable[[], Awaitable[Any]],
) -> Any:
    try:
        return await operation()
    except ApiError as exc:
        await service.audit_failure(action, target_type, target_id, exc.code)
        raise


@router.get("/users")
async def list_users(
    request: Request,
    session: DbSession,
    context: UsersManager,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    q: str | None = None,
    status: str | None = None,
):
    data, total = await service_for(request, session, context).list_users(
        page, page_size, q, status
    )
    return success_response(request, data, page=page, page_size=page_size, total=total)


@router.post("/users", dependencies=[Depends(require_csrf)])
async def create_user(
    payload: UserCreate, request: Request, session: DbSession, context: UsersManager
):
    service = service_for(request, session, context)
    data = await audit_on_error(
        service, "user.created", "user", None, lambda: service.create_user(payload)
    )
    return success_response(request, data, status_code=201)


@router.patch("/users/{user_id}", dependencies=[Depends(require_csrf)])
async def update_user(
    user_id: str,
    payload: UserUpdate,
    request: Request,
    session: DbSession,
    context: UsersManager,
):
    service = service_for(request, session, context)
    data = await audit_on_error(
        service, "user.updated", "user", user_id, lambda: service.update_user(user_id, payload)
    )
    return success_response(request, data)


@router.patch("/users/{user_id}/status", dependencies=[Depends(require_csrf)])
async def update_user_status(
    user_id: str,
    payload: StatusUpdate,
    request: Request,
    session: DbSession,
    context: UsersManager,
):
    service = service_for(request, session, context)
    data = await audit_on_error(
        service,
        "user.status_changed",
        "user",
        user_id,
        lambda: service.update_user_status(user_id, payload.status),
    )
    return success_response(request, data)


@router.post("/users/{user_id}/password-reset", dependencies=[Depends(require_csrf)])
async def reset_password(
    user_id: str,
    payload: PasswordReset,
    request: Request,
    session: DbSession,
    context: UsersManager,
) -> Response:
    service = service_for(request, session, context)
    await audit_on_error(
        service,
        "user.password_reset",
        "user",
        user_id,
        lambda: service.reset_user_password(user_id, payload.new_password),
    )
    return Response(status_code=204)


@router.get("/permissions")
async def list_permissions(request: Request, session: DbSession, context: RolesManager):
    return success_response(request, await service_for(request, session, context).list_permissions())


@router.get("/roles")
async def list_roles(
    request: Request,
    session: DbSession,
    context: RolesManager,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    q: str | None = None,
    status: str | None = None,
):
    data, total = await service_for(request, session, context).list_roles(
        page, page_size, q, status
    )
    return success_response(request, data, page=page, page_size=page_size, total=total)


@router.post("/roles", dependencies=[Depends(require_csrf)])
async def create_role(
    payload: RoleCreate, request: Request, session: DbSession, context: RolesManager
):
    service = service_for(request, session, context)
    data = await audit_on_error(
        service, "role.created", "role", None, lambda: service.create_role(payload)
    )
    return success_response(request, data, status_code=201)


@router.patch("/roles/{role_id}", dependencies=[Depends(require_csrf)])
async def update_role(
    role_id: str,
    payload: RoleUpdate,
    request: Request,
    session: DbSession,
    context: RolesManager,
):
    service = service_for(request, session, context)
    data = await audit_on_error(
        service, "role.updated", "role", role_id, lambda: service.update_role(role_id, payload)
    )
    return success_response(request, data)


@router.delete("/roles/{role_id}", status_code=204, dependencies=[Depends(require_csrf)])
async def delete_role(
    role_id: str, request: Request, session: DbSession, context: RolesManager
) -> Response:
    service = service_for(request, session, context)
    await audit_on_error(
        service, "role.deleted", "role", role_id, lambda: service.delete_role(role_id)
    )
    return Response(status_code=204)


@router.get("/functions")
async def list_functions(
    request: Request, session: DbSession, context: FunctionsManager
):
    return success_response(request, await service_for(request, session, context).list_functions())


@router.post("/functions", dependencies=[Depends(require_csrf)])
async def create_function(
    payload: FunctionCreate,
    request: Request,
    session: DbSession,
    context: FunctionsManager,
):
    service = service_for(request, session, context)
    data = await audit_on_error(
        service, "function.created", "function", None, lambda: service.create_function(payload)
    )
    return success_response(request, data, status_code=201)


@router.patch("/functions/{function_id}", dependencies=[Depends(require_csrf)])
async def update_function(
    function_id: str,
    payload: FunctionUpdate,
    request: Request,
    session: DbSession,
    context: FunctionsManager,
):
    service = service_for(request, session, context)
    data = await audit_on_error(
        service,
        "function.updated",
        "function",
        function_id,
        lambda: service.update_function(function_id, payload),
    )
    return success_response(request, data)


@router.delete("/functions/{function_id}", status_code=204, dependencies=[Depends(require_csrf)])
async def delete_function(
    function_id: str, request: Request, session: DbSession, context: FunctionsManager
) -> Response:
    service = service_for(request, session, context)
    await audit_on_error(
        service,
        "function.deleted",
        "function",
        function_id,
        lambda: service.delete_function(function_id),
    )
    return Response(status_code=204)


@router.get("/audit-logs")
async def list_audit_logs(
    request: Request,
    session: DbSession,
    context: AuditViewer,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    actor_user_id: str | None = None,
    action: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
    result: str | None = None,
):
    service = service_for(request, session, context)
    try:
        from_dt = datetime.fromisoformat(created_from) if created_from else None
        to_dt = datetime.fromisoformat(created_to) if created_to else None
    except ValueError as exc:
        raise ApiError(400, "VALIDATION_ERROR", "请求参数无效", {"created_at": "时间格式无效"}) from exc
    data, total = await service.list_audit_logs(
        page,
        page_size,
        actor_user_id,
        action,
        target_type,
        target_id,
        result,
        from_dt,
        to_dt,
    )
    return success_response(request, data, page=page, page_size=page_size, total=total)
