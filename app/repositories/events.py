"""仓库事件持久化辅助函数。"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RepositoryEvent
from app.services.github_client import GitHubActivity


async def store_new_repository_events(
    session: AsyncSession,
    subscription_id: int,
    activities: list[GitHubActivity],
) -> list[RepositoryEvent]:
    """仅保存新的仓库事件，并返回本次插入的记录。"""
    unique_activities = _deduplicate_activities(activities)
    if not unique_activities:
        return []

    external_ids = [activity.external_id for activity in unique_activities]
    existing_result = await session.execute(
        select(RepositoryEvent.external_id).where(RepositoryEvent.external_id.in_(external_ids)),
    )
    existing_ids = set(existing_result.scalars().all())

    events = [
        RepositoryEvent(
            subscription_id=subscription_id,
            event_type=activity.event_type,
            external_id=activity.external_id,
            title=activity.title,
            url=activity.url,
            occurred_at=activity.occurred_at,
        )
        for activity in unique_activities
        if activity.external_id not in existing_ids
    ]
    session.add_all(events)

    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        return await store_new_repository_events(session, subscription_id, unique_activities)

    return events


async def list_repository_events(
    session: AsyncSession,
    subscription_id: int,
    occurred_since: datetime,
    occurred_before: datetime,
) -> list[RepositoryEvent]:
    """查询单个订阅在半开时间区间内的已保存事件。"""
    result = await session.execute(
        select(RepositoryEvent)
        .where(
            RepositoryEvent.subscription_id == subscription_id,
            RepositoryEvent.occurred_at >= occurred_since,
            RepositoryEvent.occurred_at < occurred_before,
        )
        .order_by(RepositoryEvent.occurred_at.desc(), RepositoryEvent.id.desc()),
    )
    return list(result.scalars().all())


def _deduplicate_activities(activities: list[GitHubActivity]) -> list[GitHubActivity]:
    """按 external_id 对抓取结果去重，并保留首次出现的记录。"""
    seen: set[str] = set()
    unique: list[GitHubActivity] = []
    for activity in activities:
        if activity.external_id in seen:
            continue
        seen.add(activity.external_id)
        unique.append(activity)
    return unique
