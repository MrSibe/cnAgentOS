from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.state.request_id = str(uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response


def success_response(
    request: Request,
    data: Any,
    status_code: int = 200,
    **metadata: Any,
) -> JSONResponse:
    meta = {"request_id": request.state.request_id, **metadata}
    return JSONResponse(
        status_code=status_code,
        content={"data": jsonable_encoder(data), "meta": meta},
    )


def register_api_support(app: FastAPI) -> None:
    app.add_middleware(RequestIdMiddleware)

    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        error: dict[str, Any] = {"code": exc.code, "message": exc.message}
        if exc.details:
            error["details"] = exc.details
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": error,
                "meta": {"request_id": request.state.request_id},
            },
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = {
            str(error["loc"][-1]): error["msg"] for error in exc.errors()
        }
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "请求参数无效",
                    "details": details,
                },
                "meta": {"request_id": request.state.request_id},
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        if exc.status_code == 404:
            code, message = "NOT_FOUND", "资源不存在"
        elif exc.status_code == 405:
            code, message = "METHOD_NOT_ALLOWED", "请求方法不允许"
        else:
            code, message = "INTERNAL_ERROR", "请求处理失败"
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {"code": code, "message": message},
                "meta": {"request_id": request.state.request_id},
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, _exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={
                "error": {"code": "INTERNAL_ERROR", "message": "服务暂不可用"},
                "meta": {"request_id": request.state.request_id},
            },
        )
