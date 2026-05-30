from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import RepositoryEvent, Subscription
from app.services.github_client import GitHubActivity
from app.services.sentinel import SentinelAgent


class FakeGitHubClient:
    def __init__(self, activities: list[GitHubActivity]) -> None:
        self.activities = activities

    async def fetch_repository_activity(
        self,
        platform: str,
        owner: str,
        repo: str,
        access_token_encrypted: str,
        since: datetime | None,
    ) -> list[GitHubActivity]:
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


async def test_sentinel_agent_collects_events_generates_report_and_sends_notification():
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
            notification_channel="team-webhook",
        )
        session.add(subscription)
        await session.commit()
        await session.refresh(subscription)

        agent = SentinelAgent(
            github_client=FakeGitHubClient(activities),
            report_renderer=FakeReportRenderer(),
            notification_sender=sender,
        )

        result = await agent.run_subscription(session, subscription.id)

    assert result.subscription_id == subscription.id
    assert result.fetched_events == 2
    assert result.stored_events == 1
    assert result.report_id is not None
    assert sender.messages == [
        (
            "team-webhook",
            f"acme_sentinel_{datetime.now(timezone.utc).date().isoformat()}",
            "acme/sentinel: Fix login regression",
        ),
    ]

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
                        occurred_at=datetime.now(timezone.utc),
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


async def test_sentinel_agent_fetches_then_generates_date_range_report_from_stored_events():
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

    assert result.fetched_events == 1
    assert result.stored_events == 1
    assert report.name == "acme_sentinel_2026-05-29_2026-05-30"
    assert report.content_markdown == "# LLM Report\n\n- Fix login regression"
    assert "Stored issue update" in llm_client.prompts[0]
    assert "Remote event should be saved" in llm_client.prompts[0]

    await engine.dispose()
