"""
订阅仓储，负责创建订阅、查询订阅列表、删除订阅，并处理重复订阅和订阅不存在等业务错误
"""
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.db.models import Subscription
from app.schemas.subscriptions import SubscriptionCreate
from app.services.tokens import encrypt_token


async def create_subscription(
    session: AsyncSession,
    payload: SubscriptionCreate,
) -> Subscription:
    """
    创建订阅
    """
    existing = await _get_subscription_by_repository(session, payload.platform, payload.owner, payload.repo)
    if existing is not None:
        raise ApiError(
            status_code=409,
            code="subscription_conflict",
            message="该仓库已订阅。",
        )

    # 唯一性由数据库约束兜底，避免并发创建重复订阅。
    subscription = Subscription(
        platform=payload.platform,
        owner=payload.owner,
        repo=payload.repo,
        repository_url=payload.normalized_repository_url,
        interval_seconds=payload.interval_seconds,
        access_token_encrypted=(
            encrypt_token(payload.access_token.get_secret_value())
            if payload.access_token is not None
            else None
        ),
        notification_channel=payload.notification_channel,
    )
    session.add(subscription)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ApiError(
            status_code=409,
            code="subscription_conflict",
            message="该仓库已订阅。",
        ) from exc
    await session.refresh(subscription)
    return subscription


async def list_subscriptions(session: AsyncSession) -> list[Subscription]:
    """查询所有订阅，并按主键升序返回稳定结果。"""
    # 固定排序保证接口响应稳定，便于前端和测试断言。
    result = await session.execute(select(Subscription).order_by(Subscription.id))
    return list(result.scalars().all())


async def _get_subscription_by_repository(
    session: AsyncSession,
    platform: str,
    owner: str,
    repo: str,
) -> Subscription | None:
    """
    根据仓库路径查询订阅
    """
    result = await session.execute(
        select(Subscription).where(
            Subscription.platform == platform,
            Subscription.owner == owner,
            Subscription.repo == repo,
        ),
    )
    return result.scalar_one_or_none()


async def delete_subscription(session: AsyncSession, subscription_id: int) -> None:
    """删除指定订阅；订阅不存在时抛出结构化业务错误。"""
    # 删除前先查找实体，以便返回明确的业务错误。
    subscription = await session.get(Subscription, subscription_id)
    if subscription is None:
        raise ApiError(
            status_code=404,
            code="subscription_not_found",
            message="订阅不存在。",
        )

    await session.delete(subscription)
    await session.commit()
