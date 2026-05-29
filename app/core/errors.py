"""
错误模块，负责定义统一处理 API 错误。
"""

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.schemas.responses import error_response


class ErrorResponse(BaseModel):
    """旧版错误响应模型，保留用于文档表达错误字段含义。"""

    # 对外统一错误结构，避免泄露内部异常细节。
    code: str
    message: str
    trace_id: str | None = None


class ApiError(Exception):
    """可预期业务异常，最终由全局异常处理器转成统一 JSON 响应。"""

    # 业务可预期错误使用具名 code，调用方可以稳定处理。
    def __init__(self, status_code: int, code: str, message: str) -> None:
        """保存 HTTP 状态码、业务错误码和对外中文提示。"""
        self.status_code = status_code
        self.code = code
        self.message = message


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    """将业务异常转换为统一 API 错误响应。"""
    # 透传请求 ID 作为 trace_id，便于日志和客户端问题排查关联。
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(
            code=exc.status_code,
            message=exc.message,
            error_code=exc.code,
        ),
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """将请求参数校验异常转换为统一中文错误响应。"""
    return JSONResponse(
        status_code=422,
        content=error_response(
            code=422,
            message="请求参数不合法。",
            error_code="validation_error",
        ),
    )
