from datetime import datetime, timezone

from app.api.deps import get_sentinel_agent
from app.services.github_client import GitHubActivity
from app.services.sentinel import SentinelAgent


class FakeGitHubClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    async def fetch_repository_activity(
        self,
        platform: str,
        owner: str,
        repo: str,
        access_token_encrypted: str,
        since: datetime | None,
    ) -> list[GitHubActivity]:
        self.calls.append((platform, owner, repo))
        return [
            GitHubActivity(
                external_id="github:event-1",
                event_type="PushEvent",
                title="补充抓取逻辑",
                url="https://github.com/acme/sentinel",
                occurred_at=datetime(2026, 5, 29, tzinfo=timezone.utc),
            ),
        ]


class FakeReportRenderer:
    def render_digest(self, owner: str, repo: str, activities: list[GitHubActivity]) -> str:
        return f"{owner}/{repo} 新增 {len(activities)} 条动态"


class FakeNotificationSender:
    async def send(self, channel: str, subject: str, body: str) -> None:
        return None


async def test_run_subscription_endpoint_fetches_events_and_generates_report(client):
    fake_client = FakeGitHubClient()

    async def override_get_sentinel_agent() -> SentinelAgent:
        return SentinelAgent(
            github_client=fake_client,
            report_renderer=FakeReportRenderer(),
            notification_sender=FakeNotificationSender(),
        )

    client._transport.app.dependency_overrides[get_sentinel_agent] = override_get_sentinel_agent

    create_response = await client.post(
        "/api/subscriptions",
        json={
            "repository_url": "https://github.com/acme/sentinel",
            "interval_seconds": 60,
        },
    )
    subscription_id = create_response.json()["data"]["id"]

    run_response = await client.post(f"/api/subscriptions/{subscription_id}/run")

    assert run_response.status_code == 200
    payload = run_response.json()
    assert payload["success"] is True
    assert payload["data"]["subscription_id"] == subscription_id
    assert payload["data"]["fetched_events"] == 1
    assert payload["data"]["stored_events"] == 1
    assert payload["data"]["report_id"] is not None
    assert fake_client.calls == [("github", "acme", "sentinel")]

    reports_response = await client.get("/api/reports")
    reports = reports_response.json()["data"]
    assert reports[0]["title"] == "acme/sentinel 仓库更新摘要（60 秒订阅）"
    assert reports[0]["summary"] == "acme/sentinel 新增 1 条动态"
