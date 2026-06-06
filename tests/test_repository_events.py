from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import Subscription
from app.repositories.events import store_new_repository_events
from app.services.github_client import GitHubActivity


async def test_store_new_repository_events_deduplicates_per_subscription():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    occurred_at = datetime(2026, 6, 3, 8, 56, 44, tzinfo=timezone.utc)
    activity = GitHubActivity(
        external_id="gitee:1511775657676091392:commit:5bb5bc7",
        event_type="PushEvent",
        title="fullRotes 更新",
        url="https://gitee.com/giteexhcode/xl-frontend/commit/5bb5bc7",
        occurred_at=occurred_at,
    )

    async with session_factory() as session:
        first = Subscription(
            platform="gitee",
            owner="giteexhcode",
            repo="xl-frontend",
            repository_url="https://gitee.com/giteexhcode/xl-frontend",
        )
        second = Subscription(
            platform="gitee",
            owner="giteexhcode",
            repo="xl-frontend",
            repository_url="https://gitee.com/giteexhcode/xl-frontend",
            user_id=2,
        )
        session.add_all([first, second])
        await session.commit()
        await session.refresh(first)
        await session.refresh(second)

        first_events = await store_new_repository_events(session, first.id, [activity])
        second_events = await store_new_repository_events(session, second.id, [activity])
        duplicate_second_events = await store_new_repository_events(session, second.id, [activity])

    assert len(first_events) == 1
    assert len(second_events) == 1
    assert duplicate_second_events == []

    await engine.dispose()
