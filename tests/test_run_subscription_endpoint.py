from datetime import datetime, timezone

from app.api.deps import get_sentinel_agent
from app.services.github_client import GitHubActivity
from app.services.sentinel import SentinelAgent


class FakeGitHubClient:
    def __init__(self) -> None:
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
        return [
            GitHubActivity(
                external_id="github:event-1",
                event_type="PushEvent",
                title="Add report flow",
                url="https://github.com/acme/sentinel",
                occurred_at=datetime(2026, 5, 29, tzinfo=timezone.utc),
            ),
            GitHubActivity(
                external_id="github:event-1",
                event_type="PushEvent",
                title="Add report flow",
                url="https://github.com/acme/sentinel",
                occurred_at=datetime(2026, 5, 29, tzinfo=timezone.utc),
            ),
        ]


class FakeReportRenderer:
    def render_digest(self, owner: str, repo: str, activities: list[GitHubActivity]) -> str:
        titles = ", ".join(activity.title for activity in activities)
        return f"# {owner}/{repo}\n\n{titles}"


class FakeNotificationSender:
    async def send(self, channel: str, subject: str, body: str) -> None:
        return None


async def _create_subscription(client) -> int:
    create_response = await client.post(
        "/api/subscriptions",
        json={
            "repository_url": "https://github.com/acme/sentinel",
            "interval_seconds": 60,
        },
    )
    return create_response.json()["data"]["id"]


async def test_run_subscription_endpoint_is_removed(client):
    fake_client = FakeGitHubClient()

    async def override_get_sentinel_agent() -> SentinelAgent:
        return SentinelAgent(
            github_client=fake_client,
            report_renderer=FakeReportRenderer(),
            notification_sender=FakeNotificationSender(),
        )

    client._transport.app.dependency_overrides[get_sentinel_agent] = override_get_sentinel_agent
    subscription_id = await _create_subscription(client)

    run_response = await client.post(f"/api/subscriptions/{subscription_id}/run")

    assert run_response.status_code == 404
    assert fake_client.calls == []


async def test_generate_historical_report_with_date_range_uses_stored_events_only(client):
    fake_client = FakeGitHubClient()

    async def override_get_sentinel_agent() -> SentinelAgent:
        return SentinelAgent(
            github_client=fake_client,
            report_renderer=FakeReportRenderer(),
            notification_sender=FakeNotificationSender(),
        )

    client._transport.app.dependency_overrides[get_sentinel_agent] = override_get_sentinel_agent
    subscription_id = await _create_subscription(client)

    response = await client.post(
        f"/api/subscriptions/{subscription_id}/reports",
        json={"start_date": "2026-05-29", "end_date": "2026-05-30"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["subscription_id"] == subscription_id
    assert payload["data"]["name"] == "acme_sentinel_2026-05-29_2026-05-30"
    assert payload["data"]["content_markdown"] == "# acme/sentinel\n\n"
    assert fake_client.calls == []
