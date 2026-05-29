"""
健康检查路由，用于验证服务是否正常运行。
"""
from fastapi import APIRouter

from app.schemas.responses import ApiResponse, success_response

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=ApiResponse)
async def health_check() -> dict[str, object]:
    """返回服务健康状态，供 Dashboard 和外部探活调用。"""
    # 轻量健康检查，后续可扩展数据库、调度器等依赖状态。
    return success_response({"status": "ok"})
