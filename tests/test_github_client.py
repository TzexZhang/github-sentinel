from datetime import datetime, timezone

import httpx

from app.services.github_client import HttpRepositoryClient
from app.services.tokens import encrypt_token


async def test_http_repository_client_fetches_github_events_with_optional_token():
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json=[
                {
                    "id": "event-1",
                    "type": "PushEvent",
                    "created_at": "2026-05-29T08:30:00Z",
                    "repo": {"name": "octo/demo"},
                    "payload": {
                        "commits": [
                            {
                                "sha": "abc123",
                                "message": "Add dashboard fetch button",
                                "url": "https://api.github.com/repos/octo/demo/commits/abc123",
                            },
                            {
                                "sha": "def456",
                                "message": "Document report filter",
                                "url": "https://api.github.com/repos/octo/demo/commits/def456",
                            },
                        ],
                    },
                },
            ],
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = HttpRepositoryClient(http_client=http_client)
        activities = await client.fetch_repository_activity(
            platform="github",
            owner="octo",
            repo="demo",
            access_token_encrypted=encrypt_token("ghp_secret"),
            since=None,
        )

    assert requests[0].url == httpx.URL("https://api.github.com/repos/octo/demo/events")
    assert requests[0].headers["authorization"] == "Bearer ghp_secret"
    assert len(activities) == 2
    assert activities[0].external_id == "github:event-1:commit:abc123"
    assert activities[0].event_type == "PushEvent"
    assert activities[0].title == "Add dashboard fetch button"
    assert activities[0].url == "https://github.com/octo/demo/commit/abc123"
    assert activities[0].occurred_at == datetime(2026, 5, 29, 8, 30, tzinfo=timezone.utc)
    assert activities[1].external_id == "github:event-1:commit:def456"
    assert activities[1].title == "Document report filter"
    assert activities[1].url == "https://github.com/octo/demo/commit/def456"


async def test_http_repository_client_fetches_gitee_events_without_token():
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json=[
                {
                    "id": 42,
                    "type": "IssueEvent",
                    "created_at": "2026-05-29T09:00:00+08:00",
                    "human_name": "创建了 Issue",
                    "target": {
                        "title": "支持 Gitee 仓库抓取",
                        "html_url": "https://gitee.com/oschina/gitee/issues/I1",
                    },
                },
            ],
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = HttpRepositoryClient(http_client=http_client)
        activities = await client.fetch_repository_activity(
            platform="gitee",
            owner="oschina",
            repo="gitee",
            access_token_encrypted="",
            since=None,
        )

    assert requests[0].url == httpx.URL("https://gitee.com/api/v5/repos/oschina/gitee/events")
    assert "authorization" not in requests[0].headers
    assert activities[0].external_id == "gitee:42"
    assert activities[0].event_type == "IssueEvent"
    assert activities[0].title == "支持 Gitee 仓库抓取"
    assert activities[0].url == "https://gitee.com/oschina/gitee/issues/I1"


async def test_http_repository_client_extracts_gitee_push_commit_messages():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "id": "push-1",
                    "type": "PushEvent",
                    "created_at": "2026-05-29T09:00:00+08:00",
                    "payload": {
                        "commits": [
                            {"sha": "111aaa", "message": "feat: 支持报告筛选"},
                            {"sha": "222bbb", "message": "fix: 完善提交说明展示"},
                        ],
                    },
                },
            ],
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = HttpRepositoryClient(http_client=http_client)
        activities = await client.fetch_repository_activity(
            platform="gitee",
            owner="oschina",
            repo="gitee",
            access_token_encrypted="",
            since=None,
        )

    assert [activity.external_id for activity in activities] == [
        "gitee:push-1:commit:111aaa",
        "gitee:push-1:commit:222bbb",
    ]
    assert [activity.title for activity in activities] == [
        "feat: 支持报告筛选",
        "fix: 完善提交说明展示",
    ]
