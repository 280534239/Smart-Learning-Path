"""统一异常响应处理。"""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.response import ApiResponse


def build_error_response(
    *,
    status_code: int,
    message: str,
    data: Any = None,
) -> JSONResponse:
    """按统一结构构造错误响应。"""
    payload = ApiResponse[Any](
        code=status_code,
        message=message,
        data=data,
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump())


async def http_exception_handler(
    _: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    """处理 HTTP 异常。"""
    message = exc.detail if isinstance(exc.detail, str) else "请求失败"
    return build_error_response(status_code=exc.status_code, message=message)


async def validation_exception_handler(
    _: Request,
    __: RequestValidationError,
) -> JSONResponse:
    """处理请求参数校验异常。"""
    return build_error_response(
        status_code=422,
        message="请求参数校验失败",
    )


def register_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器。"""
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
