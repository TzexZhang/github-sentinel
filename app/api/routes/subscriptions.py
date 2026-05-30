"""
订阅管理路由，用于创建、查询和删除订阅。
"""

from fastapi import APIRouter

from app.api.deps import DbSession, SentinelAgentDep
from app.repositories.subscriptions import (
    create_subscription,
    delete_subscription,
    list_subscriptions,
)
from app.repositories.reports import list_reports
from app.schemas.reports import ReportGenerateRequest, ReportRead
from app.schemas.responses import ApiResponse, success_response
from app.schemas.subscriptions import SubscriptionCreate, SubscriptionRead

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])

"""
创建订阅路由，用于创建新的订阅记录。
"""
@router.post("", response_model=ApiResponse, status_code=201)
async def create_subscription_endpoint(
    payload: SubscriptionCreate,
    session: DbSession,
) -> dict[str, object]:
    """创建新的仓库订阅，访问令牌会在仓储层加密后入库。"""
    # 创建订阅前的字段校验由 SubscriptionCreate 完成，仓储层负责唯一性约束。
    subscription = await create_subscription(session, payload)
    return success_response(SubscriptionRead.model_validate(subscription).model_dump(), code=201)

"""
查询订阅路由，用于获取所有订阅列表。
"""
@router.get("", response_model=ApiResponse)
async def list_subscriptions_endpoint(session: DbSession) -> dict[str, object]:
    """查询全部订阅记录，供 Dashboard 和 API 调用方展示。"""
    # 订阅列表按创建顺序返回，方便前端稳定展示。
    subscriptions = await list_subscriptions(session)
    data = [
        SubscriptionRead.model_validate(subscription).model_dump()
        for subscription in subscriptions
    ]
    return success_response(data)


@router.post("/{subscription_id}/run", response_model=ApiResponse)
async def run_subscription_endpoint(
    subscription_id: int,
    session: DbSession,
    sentinel_agent: SentinelAgentDep,
) -> dict[str, object]:
    """立即执行一次订阅抓取，并在有新事件时生成仓库报告。"""
    result = await sentinel_agent.run_subscription(session, subscription_id)
    return success_response(
        {
            "subscription_id": result.subscription_id,
            "fetched_events": result.fetched_events,
            "stored_events": result.stored_events,
            "report_id": result.report_id,
            "notification_sent": result.notification_sent,
        },
    )


@router.post("/{subscription_id}/reports", response_model=ApiResponse, status_code=201)
async def generate_subscription_report_endpoint(
    subscription_id: int,
    payload: ReportGenerateRequest,
    session: DbSession,
    sentinel_agent: SentinelAgentDep,
) -> dict[str, object]:
    """按用户选择的日期范围抓取仓库事件、去重入库，并生成 Markdown 报告。"""
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
) -> dict[str, object]:
    """查询指定订阅仓库绑定的报告列表，并返回 Markdown 报告正文。"""
    reports = await list_reports(session, subscription_id=subscription_id)
    data = [ReportRead.model_validate(report).model_dump() for report in reports]
    return success_response(data)


"""
删除订阅路由，用于根据订阅 ID删除指定订阅。
"""
@router.delete("/{subscription_id}", response_model=ApiResponse)
async def delete_subscription_endpoint(subscription_id: int, session: DbSession) -> dict[str, object]:
    """删除指定订阅；不存在时返回中文结构化错误。"""
    # 删除不存在的订阅时返回结构化 404，避免调用方解析字符串错误。
    await delete_subscription(session, subscription_id)
    return success_response(None)
