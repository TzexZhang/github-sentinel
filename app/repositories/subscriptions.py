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
    user_id: int = 1,
) -> Subscription:
    existing = await _get_subscription_by_repository(
        session,
        user_id,
        payload.platform,
        payload.owner,
        payload.repo,
    )
    if existing is not None:
        raise _subscription_conflict()

    _validate_unique_channel_names(payload.notification_channels)

    subscription = Subscription(
        user_id=user_id,
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
            channel = _build_notification_channel(channel_payload, user_id)
            session.add(channel)
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
        raise _subscription_conflict() from exc

    await session.refresh(subscription, attribute_names=["notification_channels"])
    return subscription


async def list_subscriptions(session: AsyncSession, user_id: int | None = None) -> list[Subscription]:
    statement = select(Subscription).options(selectinload(Subscription.notification_channels))
    if user_id is not None:
        statement = statement.where(Subscription.user_id == user_id)
    result = await session.execute(statement.order_by(Subscription.id))
    return list(result.scalars().all())


async def get_subscription(
    session: AsyncSession,
    subscription_id: int,
    user_id: int | None = None,
) -> Subscription | None:
    statement = (
        select(Subscription)
        .options(selectinload(Subscription.notification_channels))
        .where(Subscription.id == subscription_id)
    )
    if user_id is not None:
        statement = statement.where(Subscription.user_id == user_id)
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def update_subscription(
    session: AsyncSession,
    subscription_id: int,
    payload: SubscriptionUpdate,
    user_id: int | None = None,
) -> Subscription:
    subscription = await get_subscription(session, subscription_id, user_id)
    if subscription is None:
        raise _subscription_not_found()

    old_channel_ids = [channel.id for channel in subscription.notification_channels]
    subscription.interval_seconds = payload.interval_seconds
    subscription.notification_channels.clear()
    await session.flush()

    for channel_payload in payload.notification_channels:
        channel = _build_notification_channel(channel_payload, subscription.user_id)
        session.add(channel)
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


async def delete_subscription(
    session: AsyncSession,
    subscription_id: int,
    user_id: int | None = None,
) -> None:
    subscription = await get_subscription(session, subscription_id, user_id)
    if subscription is None:
        raise _subscription_not_found()

    channel_ids = [channel.id for channel in subscription.notification_channels]

    await session.execute(delete(NotificationJob).where(NotificationJob.subscription_id == subscription_id))
    await session.execute(delete(Report).where(Report.subscription_id == subscription_id))
    await session.execute(delete(RepositoryEvent).where(RepositoryEvent.subscription_id == subscription_id))
    subscription.notification_channels.clear()
    await session.flush()
    await session.delete(subscription)
    for channel_id in channel_ids:
        await _delete_notification_channel_if_unused(session, channel_id)
    await session.commit()


async def _get_subscription_by_repository(
    session: AsyncSession,
    user_id: int,
    platform: str,
    owner: str,
    repo: str,
) -> Subscription | None:
    result = await session.execute(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.platform == platform,
            Subscription.owner == owner,
            Subscription.repo == repo,
        ),
    )
    return result.scalar_one_or_none()


def _build_notification_channel(
    payload: NotificationChannelCreate,
    user_id: int,
) -> NotificationChannel:
    return NotificationChannel(
        user_id=user_id,
        name=payload.name,
        channel_type=payload.channel_type,
        target=payload.target,
    )


def _validate_unique_channel_names(channels: list[NotificationChannelCreate]) -> None:
    seen: set[str] = set()
    for channel in channels:
        if channel.name in seen:
            raise ApiError(
                status_code=409,
                code="notification_channel_conflict",
                message="通知通道名称重复。",
            )
        seen.add(channel.name)


async def _delete_notification_channel_if_unused(
    session: AsyncSession,
    channel_id: int,
) -> None:
    result = await session.execute(
        select(SubscriptionNotificationChannel.id).where(
            SubscriptionNotificationChannel.notification_channel_id == channel_id,
        ),
    )
    if result.first() is not None:
        return
    job_result = await session.execute(
        select(NotificationJob.id).where(NotificationJob.notification_channel_id == channel_id),
    )
    if job_result.first() is not None:
        return
    channel = await session.get(NotificationChannel, channel_id)
    if channel is not None:
        await session.delete(channel)


def _subscription_conflict() -> ApiError:
    return ApiError(
        status_code=409,
        code="subscription_conflict",
        message="该仓库已订阅。",
    )


def _subscription_not_found() -> ApiError:
    return ApiError(
        status_code=404,
        code="subscription_not_found",
        message="订阅不存在。",
    )
