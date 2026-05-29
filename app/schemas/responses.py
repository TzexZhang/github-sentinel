from typing import Any

from pydantic import BaseModel


class ApiResponse(BaseModel):
    """统一 API 响应结构，成功和失败都保持 code/data/success 三字段。"""

    code: int
    data: Any | None
    success: bool


def success_response(data: Any | None = None, code: int = 200) -> dict[str, Any]:
    """构造统一成功响应。"""
    return {"code": code, "data": data, "success": True}


def error_response(
    code: int,
    message: str,
    error_code: str,
) -> dict[str, Any]:
    """构造统一失败响应，错误详情放在 data 内。"""
    return {
        "code": code,
        "data": {"message": message, "error_code": error_code},
        "success": False,
    }
