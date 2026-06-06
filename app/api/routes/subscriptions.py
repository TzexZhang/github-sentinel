"""
订阅管理路由，用于创建、查询和删除订阅，以及按日期范围手动生成报告。
"""

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession, SentinelAgentDep
from app.core.errors import ApiError
from app.repositories.reports import list_reports
from app.repositories.subscriptions import (
    create_subscription,
    delete_subscription,
    get_subscription,
    list_subscriptions,
    update_subscription,
)
from app.schemas.reports import ReportGenerateRequest, ReportRead
from app.schemas.responses import ApiResponse, success_response
from app.schemas.subscriptions import SubscriptionCreate, SubscriptionRead, SubscriptionUpdate

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.post("", response_model=ApiResponse, status_code=201)
async def create_subscription_endpoint(
    payload: SubscriptionCreate,
    session: DbSession,
    current_user: CurrentUser,
) -> dict[str, object]:
    """创建新的仓库订阅，访问令牌会在仓储层加密后入库。"""
    subscription = await create_subscription(session, payload, user_id=current_user.user.id)
    return success_response(SubscriptionRead.model_validate(subscription).model_dump(), code=201)


@router.get("", response_model=ApiResponse)
async def list_subscriptions_endpoint(
    session: DbSession,
    current_user: CurrentUser,
) -> dict[str, object]:
    """查询全部订阅记录，供 Dashboard 和 API 调用方展示。"""
    subscriptions = await list_subscriptions(session, user_id=current_user.user.id)
    data = [
        SubscriptionRead.model_validate(subscription).model_dump()
        for subscription in subscriptions
    ]
    return success_response(data)


@router.patch("/{subscription_id}", response_model=ApiResponse)
async def update_subscription_endpoint(
    subscription_id: int,
    payload: SubscriptionUpdate,
    session: DbSession,
    current_user: CurrentUser,
) -> dict[str, object]:
    """更新订阅间隔和通知通道配置，不允许修改仓库地址。"""
    subscription = await update_subscription(
        session,
        subscription_id,
        payload,
        user_id=current_user.user.id,
    )
    return success_response(SubscriptionRead.model_validate(subscription).model_dump())


@router.post("/{subscription_id}/reports", response_model=ApiResponse, status_code=201)
async def generate_subscription_report_endpoint(
    subscription_id: int,
    payload: ReportGenerateRequest,
    session: DbSession,
    sentinel_agent: SentinelAgentDep,
    current_user: CurrentUser,
) -> dict[str, object]:
    """按用户选择的日期范围手动生成 Markdown 报告。"""
    if await get_subscription(session, subscription_id, user_id=current_user.user.id) is None:
        raise ApiError(status_code=404, code="subscription_not_found", message="订阅不存在。")
    _, report = await sentinel_agent.generate_report_for_date_range(
        session,
        subscription_id,
        payload.start_date,
        payload.end_date,
    )
    return success_response(ReportRead.model_validate(report).model_dump(), code=201)


@router.get("/{subscription_id}/reports", response_model=ApiResponse)
async def list_subscription_reports_endpoint(
    subscription_id: int,
    session: DbSession,
    current_user: CurrentUser,
) -> dict[str, object]:
    """查询指定订阅仓库绑定的报告列表，并返回 Markdown 报告正文。"""
    if await get_subscription(session, subscription_id, user_id=current_user.user.id) is None:
        raise ApiError(status_code=404, code="subscription_not_found", message="订阅不存在。")
    reports = await list_reports(
        session,
        subscription_id=subscription_id,
        user_id=current_user.user.id,
    )
    data = [ReportRead.model_validate(report).model_dump() for report in reports]
    return success_response(data)


@router.delete("/{subscription_id}", response_model=ApiResponse)
async def delete_subscription_endpoint(
    subscription_id: int,
    session: DbSession,
    current_user: CurrentUser,
) -> dict[str, object]:
    """删除指定订阅；不存在时返回中文结构化错误。"""
    await delete_subscription(session, subscription_id, user_id=current_user.user.id)
    return success_response(None)
