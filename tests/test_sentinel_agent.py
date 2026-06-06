from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import (
    NotificationChannel,
    NotificationJob,
    Report,
    RepositoryEvent,
    Subscription,
    SubscriptionNotificationChannel,
)
from app.services.github_client import GitHubActivity
from app.services.sentinel import SentinelAgent


class FakeGitHubClient:
    def __init__(self, activities: list[GitHubActivity]) -> None:
        self.activities = activities
        self.calls: list[tuple[str, str, str, datetime | None]] = []

    async def fetch_repository_activity(
        self,
        platform: str,
        owner: str,
        repo: str,
        access_token_encrypted: str,
        since: datetime | None,
    ) -> list[GitHubActivity]:
        self.calls.append((platform, owner, repo, since))
        return self.activities


class FakeReportRenderer:
    def render_digest(self, owner: str, repo: str, activities: list[GitHubActivity]) -> str:
        titles = ", ".join(activity.title for activity in activities)
        return f"{owner}/{repo}: {titles}"


class RecordingNotificationSender:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str, str]] = []

    async def send(self, channel: str, subject: str, body: str) -> None:
        self.messages.append((channel, subject, body))


class FakeLLMClient:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def generate_markdown(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return "# LLM Report\n\n- Fix login regression"


async def test_sentinel_agent_collects_events_generates_report_and_creates_notification_jobs():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    occurred_at = datetime.now(timezone.utc)
    activities = [
        GitHubActivity(
            external_id="issue-1",
            event_type="issue",
            title="Fix login regression",
            url="https://github.com/acme/sentinel/issues/1",
            occurred_at=occurred_at,
        ),
        GitHubActivity(
            external_id="issue-1",
            event_type="issue",
            title="Fix login regression",
            url="https://github.com/acme/sentinel/issues/1",
            occurred_at=occurred_at,
        ),
    ]
    sender = RecordingNotificationSender()

    async with session_factory() as session:
        subscription = Subscription(
            platform="github",
            owner="acme",
            repo="sentinel",
            repository_url="https://github.com/acme/sentinel",
            interval_seconds=86_400,
            access_token_encrypted="encrypted-token",
        )
        session.add(subscription)
        webhook = NotificationChannel(
            name="team-webhook",
            channel_type="webhook",
            target="repo-alerts",
        )
        mail = NotificationChannel(
            name="team-mail",
            channel_type="smtp",
            target="team@example.com",
        )
        session.add_all([webhook, mail])
        await session.commit()
        await session.refresh(subscription)
        await session.refresh(webhook)
        await session.refresh(mail)
        session.add_all(
            [
                SubscriptionNotificationChannel(
                    subscription_id=subscription.id,
                    notification_channel_id=webhook.id,
                ),
                SubscriptionNotificationChannel(
                    subscription_id=subscription.id,
                    notification_channel_id=mail.id,
                ),
            ],
        )
        await session.commit()

        agent = SentinelAgent(
            github_client=FakeGitHubClient(activities),
            report_renderer=FakeReportRenderer(),
            notification_sender=sender,
        )

        result = await agent.run_subscription(session, subscription.id)
        jobs = list((await session.execute(select(NotificationJob))).scalars().all())

    assert result.subscription_id == subscription.id
    assert result.fetched_events == 2
    assert result.stored_events == 1
    assert result.report_id is not None
    assert result.notification_sent is False
    assert sender.messages == []
    assert [
        (job.notification_channel_id, job.status, job.subject, job.report_id)
        for job in jobs
    ] == [
        (
            webhook.id,
            "pending",
            f"acme_sentinel_{datetime.now(timezone.utc).date().isoformat()}",
            result.report_id,
        ),
        (
            mail.id,
            "pending",
            f"acme_sentinel_{datetime.now(timezone.utc).date().isoformat()}",
            result.report_id,
        ),
    ]

    await engine.dispose()


async def test_sentinel_agent_generates_report_when_run_has_no_new_events():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    occurred_at = datetime.now(timezone.utc)
    activities = [
        GitHubActivity(
            external_id="issue-1",
            event_type="issue",
            title="Fix login regression",
            url="https://github.com/acme/sentinel/issues/1",
            occurred_at=occurred_at,
        ),
    ]
    sender = RecordingNotificationSender()

    async with session_factory() as session:
        subscription = Subscription(
            platform="github",
            owner="acme",
            repo="sentinel",
            repository_url="https://github.com/acme/sentinel",
            interval_seconds=86_400,
        )
        session.add(subscription)
        await session.commit()
        await session.refresh(subscription)
        channel = NotificationChannel(
            name="team-webhook",
            channel_type="webhook",
            target="repo-alerts",
        )
        session.add(channel)
        await session.commit()
        await session.refresh(channel)
        session.add(
            SubscriptionNotificationChannel(
                subscription_id=subscription.id,
                notification_channel_id=channel.id,
            ),
        )
        await session.commit()

        agent = SentinelAgent(
            github_client=FakeGitHubClient(activities),
            report_renderer=FakeReportRenderer(),
            notification_sender=sender,
        )

        first_result = await agent.run_subscription(session, subscription.id)
        second_result = await agent.run_subscription(session, subscription.id)
        jobs = list((await session.execute(select(NotificationJob))).scalars().all())

    assert first_result.stored_events == 1
    assert first_result.report_id is not None
    assert second_result.stored_events == 0
    assert second_result.report_id == first_result.report_id
    assert len(jobs) == 1
    assert jobs[0].dedupe_key == f"{first_result.report_id}:{channel.id}"
    assert len(sender.messages) == 0

    await engine.dispose()


async def test_manual_current_report_generates_when_no_incremental_events_or_existing_report():
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
            interval_seconds=86_400,
        )
        session.add(subscription)
        await session.commit()
        await session.refresh(subscription)

        agent = SentinelAgent(
            github_client=FakeGitHubClient([]),
            report_renderer=FakeReportRenderer(),
            notification_sender=RecordingNotificationSender(),
        )
        report_date = datetime.now(timezone.utc).date()

        result, report = await agent.generate_report_for_date_range(
            session,
            subscription.id,
            report_date,
            report_date,
        )
        reports = list((await session.execute(select(Report))).scalars().all())

    assert result.fetched_events == 0
    assert result.stored_events == 0
    assert result.report_id == report.id
    assert report.period_start_date == report_date
    assert report.period_end_date == report_date
    assert report.content_markdown == "acme/sentinel: "
    assert len(reports) == 1

    await engine.dispose()


async def test_manual_historical_existing_report_creates_notification_jobs_when_requested():
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
            interval_seconds=86_400,
        )
        channel = NotificationChannel(
            name="team-mail",
            channel_type="smtp",
            target="team@example.com",
        )
        session.add_all([subscription, channel])
        await session.commit()
        await session.refresh(subscription)
        await session.refresh(channel)
        report = Report(
            subscription_id=subscription.id,
            name="acme_sentinel_2026-06-01_2026-06-02",
            content_markdown="# report",
            generated_at=datetime(2026, 6, 2, tzinfo=timezone.utc),
            period_start_date=datetime(2026, 6, 1, tzinfo=timezone.utc).date(),
            period_end_date=datetime(2026, 6, 2, tzinfo=timezone.utc).date(),
        )
        session.add_all(
            [
                report,
                SubscriptionNotificationChannel(
                    subscription_id=subscription.id,
                    notification_channel_id=channel.id,
                ),
            ],
        )
        await session.commit()
        await session.refresh(report)

        agent = SentinelAgent(
            github_client=FakeGitHubClient([]),
            report_renderer=FakeReportRenderer(),
            notification_sender=RecordingNotificationSender(),
        )

        result, returned_report = await agent.generate_report_for_date_range(
            session,
            subscription.id,
            report.period_start_date,
            report.period_end_date,
            send_notification=True,
        )
        jobs = list((await session.execute(select(NotificationJob))).scalars().all())

    assert returned_report.id == report.id
    assert result.notification_sent is True
    assert [(job.report_id, job.notification_channel_id, job.status) for job in jobs] == [
        (report.id, channel.id, "pending"),
    ]

    await engine.dispose()


async def test_manual_historical_existing_report_creates_new_notification_job_when_requested_again():
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
            interval_seconds=86_400,
        )
        channel = NotificationChannel(
            name="team-mail",
            channel_type="smtp",
            target="team@example.com",
        )
        session.add_all([subscription, channel])
        await session.commit()
        await session.refresh(subscription)
        await session.refresh(channel)
        report = Report(
            subscription_id=subscription.id,
            name="acme_sentinel_2026-06-01_2026-06-02",
            content_markdown="# report",
            generated_at=datetime(2026, 6, 2, tzinfo=timezone.utc),
            period_start_date=datetime(2026, 6, 1, tzinfo=timezone.utc).date(),
            period_end_date=datetime(2026, 6, 2, tzinfo=timezone.utc).date(),
        )
        session.add_all(
            [
                report,
                SubscriptionNotificationChannel(
                    subscription_id=subscription.id,
                    notification_channel_id=channel.id,
                ),
            ],
        )
        await session.commit()
        await session.refresh(report)
        existing_job = NotificationJob(
            subscription_id=subscription.id,
            report_id=report.id,
            notification_channel_id=channel.id,
            subject=report.name,
            dedupe_key=f"{report.id}:{channel.id}",
            status="sent",
        )
        session.add(existing_job)
        await session.commit()

        agent = SentinelAgent(
            github_client=FakeGitHubClient([]),
            report_renderer=FakeReportRenderer(),
            notification_sender=RecordingNotificationSender(),
        )

        result, returned_report = await agent.generate_report_for_date_range(
            session,
            subscription.id,
            report.period_start_date,
            report.period_end_date,
            send_notification=True,
        )
        jobs = list(
            (
                await session.execute(select(NotificationJob).order_by(NotificationJob.id))
            )
            .scalars()
            .all(),
        )

    assert returned_report.id == report.id
    assert result.notification_sent is True
    assert [(job.report_id, job.notification_channel_id, job.status) for job in jobs] == [
        (report.id, channel.id, "sent"),
        (report.id, channel.id, "pending"),
    ]
    assert jobs[0].dedupe_key == f"{report.id}:{channel.id}"
    assert jobs[1].dedupe_key != jobs[0].dedupe_key

    await engine.dispose()


async def test_sentinel_agent_overwrites_same_day_scheduled_report_when_new_events_arrive():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    occurred_at = datetime.now(timezone.utc)
    client = FakeGitHubClient(
        [
            GitHubActivity(
                external_id="issue-1",
                event_type="issue",
                title="Fix login regression",
                url="https://github.com/acme/sentinel/issues/1",
                occurred_at=occurred_at,
            ),
        ],
    )

    async with session_factory() as session:
        subscription = Subscription(
            platform="github",
            owner="acme",
            repo="sentinel",
            repository_url="https://github.com/acme/sentinel",
            interval_seconds=86_400,
        )
        session.add(subscription)
        await session.commit()
        await session.refresh(subscription)

        agent = SentinelAgent(
            github_client=client,
            report_renderer=FakeReportRenderer(),
            notification_sender=RecordingNotificationSender(),
        )

        first_result = await agent.run_subscription(session, subscription.id)
        client.activities = [
            *client.activities,
            GitHubActivity(
                external_id="issue-2",
                event_type="issue",
                title="Add report overwrite rule",
                url="https://github.com/acme/sentinel/issues/2",
                occurred_at=occurred_at,
            ),
        ]
        second_result = await agent.run_subscription(session, subscription.id)
        reports = list((await session.execute(select(Report))).scalars().all())

    assert first_result.report_id is not None
    assert second_result.stored_events == 1
    assert second_result.report_id == first_result.report_id
    assert len(reports) == 1
    assert reports[0].period_start_date == occurred_at.date()
    assert reports[0].period_end_date == occurred_at.date()
    assert reports[0].content_markdown == "acme/sentinel: Add report overwrite rule, Fix login regression"

    await engine.dispose()


async def test_sentinel_agent_uses_llm_client_when_generating_report():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    llm_client = FakeLLMClient()

    async with session_factory() as session:
        subscription = Subscription(
            platform="github",
            owner="acme",
            repo="sentinel",
            repository_url="https://github.com/acme/sentinel",
            interval_seconds=86_400,
        )
        session.add(subscription)
        await session.commit()
        await session.refresh(subscription)

        agent = SentinelAgent(
            github_client=FakeGitHubClient(
                [
                    GitHubActivity(
                        external_id="issue-1",
                        event_type="IssuesEvent",
                        title="Fix login regression",
                        url="https://github.com/acme/sentinel/issues/1",
                        occurred_at=datetime.now(timezone.utc) - timedelta(seconds=1),
                    ),
                ],
            ),
            report_renderer=FakeReportRenderer(),
            notification_sender=RecordingNotificationSender(),
            llm_client=llm_client,
        )

        result = await agent.run_subscription(session, subscription.id)
        report = await session.get(__import__("app.db.models").db.models.Report, result.report_id)

    assert llm_client.prompts
    assert report is not None
    assert report.content_markdown == "# LLM Report\n\n- Fix login regression"

    await engine.dispose()


async def test_sentinel_agent_generates_historical_date_range_report_from_stored_events():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    llm_client = FakeLLMClient()
    github_client = FakeGitHubClient(
        [
            GitHubActivity(
                external_id="remote-event",
                event_type="PushEvent",
                title="Remote event should be saved",
                url="https://github.com/acme/sentinel/commit/remote",
                occurred_at=datetime(2026, 5, 29, tzinfo=timezone.utc),
            ),
        ],
    )

    async with session_factory() as session:
        subscription = Subscription(
            platform="github",
            owner="acme",
            repo="sentinel",
            repository_url="https://github.com/acme/sentinel",
            interval_seconds=86_400,
        )
        session.add(subscription)
        await session.flush()
        session.add(
            RepositoryEvent(
                subscription_id=subscription.id,
                event_type="IssuesEvent",
                external_id="stored-issue",
                title="Stored issue update",
                url="https://github.com/acme/sentinel/issues/1",
                occurred_at=datetime(2026, 5, 29, 12, tzinfo=timezone.utc),
            ),
        )
        await session.commit()
        await session.refresh(subscription)

        agent = SentinelAgent(
            github_client=github_client,
            report_renderer=FakeReportRenderer(),
            notification_sender=RecordingNotificationSender(),
            llm_client=llm_client,
        )

        result, report = await agent.generate_report_for_date_range(
            session,
            subscription.id,
            datetime(2026, 5, 29, tzinfo=timezone.utc).date(),
            datetime(2026, 5, 30, tzinfo=timezone.utc).date(),
        )

    assert result.fetched_events == 0
    assert result.stored_events == 0
    assert report.name == "acme_sentinel_2026-05-29_2026-05-30"
    assert report.content_markdown == "# LLM Report\n\n- Fix login regression"
    assert "Stored issue update" in llm_client.prompts[0]
    assert "Remote event should be saved" not in llm_client.prompts[0]
    assert github_client.calls == []

    await engine.dispose()


async def test_sentinel_agent_overwrites_existing_report_for_same_date_range():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    llm_client = FakeLLMClient()

    async with session_factory() as session:
        subscription = Subscription(
            platform="github",
            owner="acme",
            repo="sentinel",
            repository_url="https://github.com/acme/sentinel",
            interval_seconds=86_400,
        )
        session.add(subscription)
        await session.commit()
        await session.refresh(subscription)

        agent = SentinelAgent(
            github_client=FakeGitHubClient([]),
            report_renderer=FakeReportRenderer(),
            notification_sender=RecordingNotificationSender(),
            llm_client=llm_client,
        )

        _, first = await agent.generate_report_for_date_range(
            session,
            subscription.id,
            datetime(2026, 5, 29, tzinfo=timezone.utc).date(),
            datetime(2026, 5, 30, tzinfo=timezone.utc).date(),
        )
        _, second = await agent.generate_report_for_date_range(
            session,
            subscription.id,
            datetime(2026, 5, 29, tzinfo=timezone.utc).date(),
            datetime(2026, 5, 30, tzinfo=timezone.utc).date(),
        )

    assert second.id == first.id
    assert second.period_start_date.isoformat() == "2026-05-29"
    assert second.period_end_date.isoformat() == "2026-05-30"

    await engine.dispose()


async def test_manual_historical_report_returns_existing_without_fetching_remote_events():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    client = FakeGitHubClient(
        [
            GitHubActivity(
                external_id="remote-event",
                event_type="PushEvent",
                title="Remote event should not be fetched",
                url="https://github.com/acme/sentinel/commit/remote",
                occurred_at=datetime(2026, 5, 29, tzinfo=timezone.utc),
            ),
        ],
    )

    async with session_factory() as session:
        subscription = Subscription(
            platform="github",
            owner="acme",
            repo="sentinel",
            repository_url="https://github.com/acme/sentinel",
            interval_seconds=86_400,
        )
        session.add(subscription)
        await session.flush()
        existing = Report(
            subscription_id=subscription.id,
            name="acme_sentinel_2026-05-29_2026-05-30",
            content_markdown="# Existing report",
            generated_at=datetime(2026, 5, 31, tzinfo=timezone.utc),
            period_start_date=datetime(2026, 5, 29, tzinfo=timezone.utc).date(),
            period_end_date=datetime(2026, 5, 30, tzinfo=timezone.utc).date(),
        )
        session.add(existing)
        await session.commit()
        await session.refresh(subscription)
        await session.refresh(existing)

        agent = SentinelAgent(
            github_client=client,
            report_renderer=FakeReportRenderer(),
            notification_sender=RecordingNotificationSender(),
        )

        result, report = await agent.generate_report_for_date_range(
            session,
            subscription.id,
            datetime(2026, 5, 29, tzinfo=timezone.utc).date(),
            datetime(2026, 5, 30, tzinfo=timezone.utc).date(),
        )

    assert client.calls == []
    assert result.fetched_events == 0
    assert result.stored_events == 0
    assert result.report_id == existing.id
    assert report.id == existing.id
    assert report.content_markdown == "# Existing report"

    await engine.dispose()
