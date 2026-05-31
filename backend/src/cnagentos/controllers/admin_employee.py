"""Admin REST API for digital employee and tool management (Phase 7)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from cnagentos.api import success_response
from cnagentos.controllers.dependencies import (
    CurrentContext,
    DbSession,
    require_csrf,
    require_permission,
)
from cnagentos.schemas import (
    DigitalEmployeeCreate,
    DigitalEmployeeUpdate,
    StatusUpdate,
    ToolBindRequest,
    ToolCreate,
    ToolUpdate,
)
from cnagentos.services.employee import DigitalEmployeeService
from cnagentos.services.tool import ToolService

router = APIRouter(prefix="/api/v1/admin", tags=["管理端-数字员工与工具"])

# Permission guards
EmployeeAdmin = Annotated[CurrentContext, Depends(require_permission("employee.manage"))]
ToolAdmin = Annotated[CurrentContext, Depends(require_permission("tools.manage"))]
ToolViewer = Annotated[CurrentContext, Depends(require_permission("tools.view"))]


def emp_service(request: Request, session: DbSession, context: CurrentContext) -> DigitalEmployeeService:
    return DigitalEmployeeService(
        session, context.user, request.client.host if request.client else None,
    )


def tool_service(request: Request, session: DbSession, context: CurrentContext) -> ToolService:
    return ToolService(
        session, context.user, request.client.host if request.client else None,
    )


# =============================================================================
# Digital Employee CRUD
# =============================================================================


@router.get("/digital-employees")
async def list_employees(
    request: Request,
    session: DbSession,
    context: EmployeeAdmin,
    q: str | None = Query(default=None),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    svc = emp_service(request, session, context)
    data, total = await svc.list_employees(page, page_size, q, status)
    return success_response(request, data, page=page, page_size=page_size, total=total)


@router.post("/digital-employees", status_code=201)
async def create_employee(
    request: Request,
    session: DbSession,
    context: EmployeeAdmin,
    payload: DigitalEmployeeCreate,
    _=Depends(require_csrf),
):
    svc = emp_service(request, session, context)
    return success_response(request, await svc.create_employee(payload), status_code=201)


@router.get("/digital-employees/{employee_id}")
async def get_employee(
    request: Request,
    session: DbSession,
    context: EmployeeAdmin,
    employee_id: str,
):
    svc = emp_service(request, session, context)
    return success_response(request, await svc.get_employee(employee_id))


@router.patch("/digital-employees/{employee_id}")
async def update_employee(
    request: Request,
    session: DbSession,
    context: EmployeeAdmin,
    employee_id: str,
    payload: DigitalEmployeeUpdate,
    _=Depends(require_csrf),
):
    svc = emp_service(request, session, context)
    return success_response(request, await svc.update_employee(employee_id, payload))


@router.patch("/digital-employees/{employee_id}/status")
async def update_employee_status(
    request: Request,
    session: DbSession,
    context: EmployeeAdmin,
    employee_id: str,
    payload: StatusUpdate,
    _=Depends(require_csrf),
):
    svc = emp_service(request, session, context)
    return success_response(request, await svc.update_employee_status(employee_id, payload.status))


# =============================================================================
# Tool bindings
# =============================================================================


@router.get("/digital-employees/{employee_id}/tools")
async def list_bound_tools(
    request: Request,
    session: DbSession,
    context: EmployeeAdmin,
    employee_id: str,
):
    svc = emp_service(request, session, context)
    return success_response(request, await svc.list_bound_tools(employee_id))


@router.post("/digital-employees/{employee_id}/tools", status_code=201)
async def bind_tool(
    request: Request,
    session: DbSession,
    context: EmployeeAdmin,
    employee_id: str,
    payload: ToolBindRequest,
    _=Depends(require_csrf),
):
    svc = emp_service(request, session, context)
    return success_response(
        request,
        await svc.bind_tool(employee_id, payload.tool_id, payload.binding_config),
        status_code=201,
    )


@router.delete("/digital-employees/{employee_id}/tools/{tool_id}")
async def unbind_tool(
    request: Request,
    session: DbSession,
    context: EmployeeAdmin,
    employee_id: str,
    tool_id: str,
    _=Depends(require_csrf),
):
    svc = emp_service(request, session, context)
    await svc.unbind_tool(employee_id, tool_id)
    return success_response(request, None)


@router.get("/digital-employees/{employee_id}/call-logs")
async def list_employee_call_logs(
    request: Request,
    session: DbSession,
    context: EmployeeAdmin,
    employee_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    svc = emp_service(request, session, context)
    data, total = await svc.list_call_logs(employee_id, page, page_size)
    return success_response(request, data, page=page, page_size=page_size, total=total)


# =============================================================================
# Tool CRUD
# =============================================================================


@router.get("/tools")
async def list_tools(
    request: Request,
    session: DbSession,
    context: ToolViewer,
    q: str | None = Query(default=None),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    svc = tool_service(request, session, context)
    data, total = await svc.list_tools(page, page_size, q, status)
    return success_response(request, data, page=page, page_size=page_size, total=total)


@router.post("/tools", status_code=201)
async def create_tool(
    request: Request,
    session: DbSession,
    context: ToolAdmin,
    payload: ToolCreate,
    _=Depends(require_csrf),
):
    svc = tool_service(request, session, context)
    return success_response(request, await svc.create_tool(payload), status_code=201)


@router.get("/tools/{tool_id}")
async def get_tool(
    request: Request,
    session: DbSession,
    context: ToolViewer,
    tool_id: str,
):
    svc = tool_service(request, session, context)
    return success_response(request, await svc.get_tool(tool_id))


@router.patch("/tools/{tool_id}")
async def update_tool(
    request: Request,
    session: DbSession,
    context: ToolAdmin,
    tool_id: str,
    payload: ToolUpdate,
    _=Depends(require_csrf),
):
    svc = tool_service(request, session, context)
    return success_response(request, await svc.update_tool(tool_id, payload))


@router.patch("/tools/{tool_id}/status")
async def update_tool_status(
    request: Request,
    session: DbSession,
    context: ToolAdmin,
    tool_id: str,
    payload: StatusUpdate,
    _=Depends(require_csrf),
):
    svc = tool_service(request, session, context)
    return success_response(request, await svc.update_tool_status(tool_id, payload.status))


@router.get("/tools/{tool_id}/bound-employees")
async def list_bound_employees(
    request: Request,
    session: DbSession,
    context: ToolViewer,
    tool_id: str,
):
    svc = tool_service(request, session, context)
    return success_response(request, await svc.list_bound_employees(tool_id))


@router.get("/tools/{tool_id}/invocation-logs")
async def list_tool_invocation_logs(
    request: Request,
    session: DbSession,
    context: ToolViewer,
    tool_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    svc = tool_service(request, session, context)
    data, total = await svc.list_invocation_logs(tool_id, page, page_size)
    return success_response(request, data, page=page, page_size=page_size, total=total)
