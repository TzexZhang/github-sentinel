from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import Subscription
from app.services.scheduler import SubscriptionScheduler, normalize_scheduler_datetime


class RecordingAgent:
    def __init__(self) -> None:
        self.calls: list[int] = []

    async def run_subscription(self, session, subscription_id: int):
        self.calls.append(subscription_id)


async def test_scheduler_runs_due_subscription_and_updates_schedule_fields():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime(2026, 6, 1, 8, tzinfo=UTC)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        subscription = Subscription(
            platform="github",
            owner="acme",
            repo="sentinel",
            repository_url="https://github.com/acme/sentinel",
            interval_seconds=60,
            next_run_at=now - timedelta(seconds=1),
        )
        session.add(subscription)
        await session.commit()
        subscription_id = subscription.id

    agent = RecordingAgent()
    scheduler = SubscriptionScheduler(session_factory=session_factory, sentinel_agent=agent)

    result = await scheduler.run_due_once(now=now)

    async with session_factory() as session:
        refreshed = await session.get(Subscription, subscription_id)

    assert result.checked == 1
    assert result.executed == 1
    assert result.failed == 0
    assert agent.calls == [subscription_id]
    assert refreshed is not None
    assert normalize_scheduler_datetime(refreshed.last_run_at) == now
    assert normalize_scheduler_datetime(refreshed.next_run_at) == now + timedelta(seconds=60)

    await engine.dispose()


async def test_scheduler_skips_subscription_before_next_run_time():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime(2026, 6, 1, 8, tzinfo=UTC)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        session.add(
            Subscription(
                platform="github",
                owner="acme",
                repo="sentinel",
                repository_url="https://github.com/acme/sentinel",
                interval_seconds=60,
                next_run_at=now + timedelta(seconds=30),
            ),
        )
        await session.commit()

    agent = RecordingAgent()
    scheduler = SubscriptionScheduler(session_factory=session_factory, sentinel_agent=agent)

    result = await scheduler.run_due_once(now=now)

    assert result.checked == 1
    assert result.executed == 0
    assert result.failed == 0
    assert agent.calls == []

    await engine.dispose()
