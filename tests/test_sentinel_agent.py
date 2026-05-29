from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import Subscription
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


async def test_sentinel_agent_collects_events_generates_report_and_sends_notification():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    occurred_at = datetime(2026, 5, 28, tzinfo=timezone.utc)
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
            "acme/sentinel 仓库更新摘要（86400 秒订阅）",
            "acme/sentinel: Fix login regression",
        ),
    ]

    await engine.dispose()
