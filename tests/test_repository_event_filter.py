import httpx

from app.services.github_client import HttpRepositoryClient


async def test_http_repository_client_keeps_only_push_and_issues_events():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "id": "push-1",
                    "type": "PushEvent",
                    "created_at": "2026-05-30T08:00:00Z",
                    "payload": {
                        "commits": [
                            {"sha": "abc123", "message": "Add LLM summary"},
                        ],
                    },
                },
                {
                    "id": "issue-1",
                    "type": "IssuesEvent",
                    "created_at": "2026-05-30T09:00:00Z",
                    "payload": {
                        "issue": {
                            "title": "Summarize issue updates",
                            "html_url": "https://github.com/acme/sentinel/issues/1",
                        },
                    },
                },
                {
                    "id": "star-1",
                    "type": "WatchEvent",
                    "created_at": "2026-05-30T10:00:00Z",
                    "payload": {},
                },
            ],
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = HttpRepositoryClient(http_client=http_client)
        activities = await client.fetch_repository_activity(
            platform="github",
            owner="acme",
            repo="sentinel",
            access_token_encrypted="",
            since=None,
        )

    assert [activity.event_type for activity in activities] == ["PushEvent", "IssuesEvent"]
    assert [activity.title for activity in activities] == [
        "Add LLM summary",
        "Summarize issue updates",
    ]
