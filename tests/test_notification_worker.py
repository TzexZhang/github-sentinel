from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import NotificationChannel, NotificationJob, Report, Subscription
from app.services.notification_worker import NotificationWorker


class RecordingNotificationRouter:
    def __init__(self) -> None:
        self.calls: list[tuple[NotificationChannel, str, str]] = []

    async def send(self, channel: NotificationChannel, subject: str, body: str) -> None:
        self.calls.append((channel, subject, body))


async def test_notification_worker_sends_pending_jobs_and_marks_sent():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        subscription = Subscription(
            platform="github",
            owner="acme",
            repo="sentinel",
            repository_url="https://github.com/acme/sentinel",
            interval_seconds=60,
        )
        channel = NotificationChannel(
            name="team-webhook",
            channel_type="webhook",
            target="release-bot",
        )
        session.add_all([subscription, channel])
        await session.commit()
        await session.refresh(subscription)
        await session.refresh(channel)
        report = Report(
            subscription_id=subscription.id,
            name="acme_sentinel_2026-06-02",
            content_markdown="# report",
            generated_at=datetime.now(timezone.utc),
        )
        session.add(report)
        await session.commit()
        await session.refresh(report)
        job = NotificationJob(
            subscription_id=subscription.id,
            report_id=report.id,
            notification_channel_id=channel.id,
            subject=report.name,
            dedupe_key=f"{report.id}:{channel.id}",
        )
        session.add(job)
        await session.commit()

    router = RecordingNotificationRouter()
    worker = NotificationWorker(session_factory=session_factory, notification_sender=router)

    result = await worker.run_pending_once()

    async with session_factory() as session:
        jobs = list((await session.execute(select(NotificationJob))).scalars().all())

    assert result.checked == 1
    assert result.sent == 1
    assert result.failed == 0
    assert [(call[0].id, call[1], call[2]) for call in router.calls] == [
        (channel.id, report.name, "# report"),
    ]
    assert jobs[0].status == "sent"
    assert jobs[0].sent_at is not None

    await engine.dispose()


async def test_notification_worker_processes_at_most_50_pending_jobs_per_run():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        subscription = Subscription(
            platform="github",
            owner="acme",
            repo="sentinel",
            repository_url="https://github.com/acme/sentinel",
            interval_seconds=60,
        )
        channel = NotificationChannel(
            name="team-webhook",
            channel_type="webhook",
            target="release-bot",
        )
        session.add_all([subscription, channel])
        await session.flush()
        for index in range(55):
            report = Report(
                subscription_id=subscription.id,
                name=f"report-{index}",
                content_markdown=f"# report {index}",
                generated_at=datetime.now(timezone.utc),
            )
            session.add(report)
            await session.flush()
            session.add(
                NotificationJob(
                    subscription_id=subscription.id,
                    report_id=report.id,
                    notification_channel_id=channel.id,
                    subject=report.name,
                    dedupe_key=f"{report.id}:{channel.id}",
                ),
            )
        await session.commit()

    router = RecordingNotificationRouter()
    worker = NotificationWorker(session_factory=session_factory, notification_sender=router)

    result = await worker.run_pending_once()

    async with session_factory() as session:
        sent_count = len(
            (
                await session.execute(
                    select(NotificationJob).where(NotificationJob.status == "sent"),
                )
            )
            .scalars()
            .all(),
        )
        pending_count = len(
            (
                await session.execute(
                    select(NotificationJob).where(NotificationJob.status == "pending"),
                )
            )
            .scalars()
            .all(),
        )

    assert result.checked == 50
    assert result.sent == 50
    assert len(router.calls) == 50
    assert sent_count == 50
    assert pending_count == 5

    await engine.dispose()
