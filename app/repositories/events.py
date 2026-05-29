"""
事件存储模块，负责存储和查询仓库事件。
仓库事件仓储，负责把 GitHub 活动转换为 `RepositoryEvent` 记录，并按 `external_id` 做幂等去重
"""
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
    """幂等存储新的仓库事件，并返回本次真正新增的记录。"""
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


def _deduplicate_activities(activities: list[GitHubActivity]) -> list[GitHubActivity]:
    """按 external_id 对抓取结果去重，保留首次出现的事件。"""
    seen: set[str] = set()
    unique: list[GitHubActivity] = []
    for activity in activities:
        if activity.external_id in seen:
            continue
        seen.add(activity.external_id)
        unique.append(activity)
    return unique
