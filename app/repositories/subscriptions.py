"""
订阅仓储，负责创建订阅、查询订阅列表、删除订阅，并处理重复订阅和订阅不存在等业务错误
"""
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import ApiError
from app.db.models import (
    NotificationChannel,
    NotificationJob,
    Report,
    RepositoryEvent,
    Subscription,
    SubscriptionNotificationChannel,
)
from app.schemas.subscriptions import NotificationChannelCreate, SubscriptionCreate, SubscriptionUpdate
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

    _validate_unique_channel_names(payload.notification_channels)

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
    )
    session.add(subscription)
    try:
        await session.flush()
        for channel_payload in payload.notification_channels:
            channel = await _get_or_create_notification_channel(session, channel_payload)
            await session.flush()
            session.add(
                SubscriptionNotificationChannel(
                    subscription_id=subscription.id,
                    notification_channel_id=channel.id,
                ),
            )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ApiError(
            status_code=409,
            code="subscription_conflict",
            message="该仓库已订阅。",
        ) from exc
    await session.refresh(subscription, attribute_names=["notification_channels"])
    return subscription


async def list_subscriptions(session: AsyncSession) -> list[Subscription]:
    """查询所有订阅，并按主键升序返回稳定结果。"""
    # 固定排序保证接口响应稳定，便于前端和测试断言。
    result = await session.execute(
        select(Subscription)
        .options(selectinload(Subscription.notification_channels))
        .order_by(Subscription.id),
    )
    return list(result.scalars().all())


async def update_subscription(
    session: AsyncSession,
    subscription_id: int,
    payload: SubscriptionUpdate,
) -> Subscription:
    """更新订阅间隔和通知通道配置。"""
    result = await session.execute(
        select(Subscription)
        .options(selectinload(Subscription.notification_channels))
        .where(Subscription.id == subscription_id),
    )
    subscription = result.scalar_one_or_none()
    if subscription is None:
        raise ApiError(
            status_code=404,
            code="subscription_not_found",
            message="订阅不存在。",
        )

    old_channel_ids = [channel.id for channel in subscription.notification_channels]
    subscription.interval_seconds = payload.interval_seconds
    subscription.notification_channels.clear()
    await session.flush()

    for channel_payload in payload.notification_channels:
        channel = await _get_or_create_notification_channel(session, channel_payload)
        await session.flush()
        session.add(
            SubscriptionNotificationChannel(
                subscription_id=subscription.id,
                notification_channel_id=channel.id,
            ),
        )

    for channel_id in old_channel_ids:
        await _delete_notification_channel_if_unused(session, channel_id)

    await session.commit()
    await session.refresh(subscription, attribute_names=["notification_channels"])
    return subscription


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


def _validate_unique_channel_names(channels: list[NotificationChannelCreate]) -> None:
    """拒绝同一次订阅请求中的重复通知通道名称。"""
    seen: set[str] = set()
    for channel in channels:
        if channel.name in seen:
            raise ApiError(
                status_code=409,
                code="notification_channel_conflict",
                message="通知通道名称重复。",
            )
        seen.add(channel.name)


async def _get_or_create_notification_channel(
    session: AsyncSession,
    payload: NotificationChannelCreate,
) -> NotificationChannel:
    """为当前订阅创建专属通知通道，避免不同仓库之间共享通道配置。"""
    channel = NotificationChannel(
        name=payload.name,
        channel_type=payload.channel_type,
        target=payload.target,
    )
    session.add(channel)
    return channel


async def delete_subscription(session: AsyncSession, subscription_id: int) -> None:
    """删除指定订阅；订阅不存在时抛出结构化业务错误。"""
    # 删除前先查找实体，以便返回明确的业务错误。
    result = await session.execute(
        select(Subscription)
        .options(selectinload(Subscription.notification_channels))
        .where(Subscription.id == subscription_id),
    )
    subscription = result.scalar_one_or_none()
    if subscription is None:
        raise ApiError(
            status_code=404,
            code="subscription_not_found",
            message="订阅不存在。",
        )

    channel_ids = [channel.id for channel in subscription.notification_channels]

    await session.execute(
        delete(NotificationJob).where(NotificationJob.subscription_id == subscription_id),
    )
    await session.execute(delete(Report).where(Report.subscription_id == subscription_id))
    await session.execute(
        delete(RepositoryEvent).where(RepositoryEvent.subscription_id == subscription_id),
    )
    subscription.notification_channels.clear()
    await session.flush()
    await session.delete(subscription)
    for channel_id in channel_ids:
        await _delete_notification_channel_if_unused(session, channel_id)
    await session.commit()


async def _delete_notification_channel_if_unused(
    session: AsyncSession,
    channel_id: int,
) -> None:
    """删除不再被任何订阅绑定的通知通道。"""
    result = await session.execute(
        select(SubscriptionNotificationChannel.id).where(
            SubscriptionNotificationChannel.notification_channel_id == channel_id,
        ),
    )
    if result.first() is not None:
        return
    job_result = await session.execute(
        select(NotificationJob.id).where(
            NotificationJob.notification_channel_id == channel_id,
        ),
    )
    if job_result.first() is not None:
        return
    channel = await session.get(NotificationChannel, channel_id)
    if channel is not None:
        await session.delete(channel)
