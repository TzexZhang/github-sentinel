from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import Subscription
from app.repositories.subscriptions import create_subscription
from app.schemas.subscriptions import SubscriptionCreate
from app.services.tokens import decrypt_token


async def test_create_github_subscription_from_repository_url(client):
    response = await client.post(
        "/api/subscriptions",
        json={
            "repository_url": "https://github.com/encode/httpx",
            "access_token": "ghp_secret_token",
            "interval_seconds": 90,
            "notification_channel": "team-webhook",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["code"] == 201
    assert payload["success"] is True
    created = payload["data"]
    assert created["platform"] == "github"
    assert created["owner"] == "encode"
    assert created["repo"] == "httpx"
    assert created["repository_url"] == "https://github.com/encode/httpx"
    assert created["token_configured"] is True
    assert created["interval_seconds"] == 90
    assert "access_token" not in created
    assert "access_token_encrypted" not in created


async def test_create_public_subscription_without_access_token(client):
    response = await client.post(
        "/api/subscriptions",
        json={
            "repository_url": "https://github.com/encode/starlette",
            "interval_seconds": 120,
        },
    )

    assert response.status_code == 201
    created = response.json()["data"]
    assert created["platform"] == "github"
    assert created["owner"] == "encode"
    assert created["repo"] == "starlette"
    assert created["token_configured"] is False


async def test_create_gitee_subscription_from_git_url(client):
    response = await client.post(
        "/api/subscriptions",
        json={
            "repository_url": "https://gitee.com/oschina/gitee.git",
            "access_token": "gitee_secret_token",
            "interval_seconds": 3600,
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["code"] == 201
    assert payload["success"] is True
    created = payload["data"]
    assert created["platform"] == "gitee"
    assert created["owner"] == "oschina"
    assert created["repo"] == "gitee"
    assert created["token_configured"] is True


async def test_create_subscription_encrypts_token_in_database():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        subscription = await create_subscription(
            session,
            SubscriptionCreate(
                repository_url="https://github.com/private-org/private-repo",
                access_token="plain_secret",
                interval_seconds=60,
            ),
        )

        result = await session.execute(select(Subscription).where(Subscription.id == subscription.id))
        stored = result.scalar_one()

    assert stored.access_token_encrypted is not None
    assert stored.access_token_encrypted != "plain_secret"
    assert decrypt_token(stored.access_token_encrypted) == "plain_secret"

    await engine.dispose()


async def test_create_subscription_requires_repository_url(client):
    response = await client.post(
        "/api/subscriptions",
        json={
            "access_token": "secret",
            "interval_seconds": 3600,
        },
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["code"] == 422
    assert payload["success"] is False
    assert payload["data"]["message"] == "请求参数不合法。"


async def test_create_subscription_rejects_unsupported_repository_host(client):
    response = await client.post(
        "/api/subscriptions",
        json={
            "repository_url": "https://gitlab.com/example/project",
            "access_token": "secret",
            "interval_seconds": 60,
        },
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["code"] == 422
    assert payload["success"] is False
    assert payload["data"]["message"] == "请求参数不合法。"


async def test_create_subscription_rejects_sub_second_interval(client):
    response = await client.post(
        "/api/subscriptions",
        json={
            "repository_url": "https://github.com/encode/httpx",
            "access_token": "secret",
            "interval_seconds": 0,
        },
    )

    assert response.status_code == 422


async def test_create_duplicate_subscription_returns_structured_conflict(client):
    payload = {
        "repository_url": "https://github.com/encode/httpx",
        "access_token": "secret",
        "interval_seconds": 3600,
    }

    first_response = await client.post("/api/subscriptions", json=payload)
    second_response = await client.post("/api/subscriptions", json=payload)

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    response_payload = second_response.json()
    assert response_payload["code"] == 409
    assert response_payload["success"] is False
    assert response_payload["data"]["error_code"] == "subscription_conflict"
    assert response_payload["data"]["message"] == "该仓库已订阅。"


async def test_delete_missing_subscription_returns_structured_error(client):
    response = await client.delete("/api/subscriptions/404")

    assert response.status_code == 404
    payload = response.json()
    assert payload["code"] == 404
    assert payload["success"] is False
    assert payload["data"]["error_code"] == "subscription_not_found"
    assert payload["data"]["message"] == "订阅不存在。"
