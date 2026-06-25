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
from app.repositories.subscriptions import create_subscription, delete_subscription
from app.schemas.subscriptions import SubscriptionCreate
from app.services.tokens import decrypt_token


async def test_create_github_subscription_from_repository_url(client):
    response = await client.post(
        "/api/subscriptions",
        json={
            "repository_url": "https://github.com/encode/httpx",
            "access_token": "ghp_secret_token",
            "interval_seconds": 90,
            "notification_channels": [
                {
                    "name": "team-webhook",
                    "channel_type": "webhook",
                    "target": "repo-alerts",
                },
            ],
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
    assert created["notification_channels"] == [
        {
            "id": 1,
            "name": "team-webhook",
            "channel_type": "webhook",
            "target": "repo-alerts",
            "is_active": True,
        },
    ]
    assert "access_token" not in created
    assert "access_token_encrypted" not in created


async def test_create_subscription_rejects_legacy_notification_channel(client):
    response = await client.post(
        "/api/subscriptions",
        json={
            "repository_url": "https://github.com/encode/httpx",
            "interval_seconds": 90,
            "notification_channel": "team-webhook",
        },
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["code"] == 422
    assert payload["success"] is False


async def test_create_subscription_rejects_smtp_channel_target_that_is_not_email(client):
    response = await client.post(
        "/api/subscriptions",
        json={
            "repository_url": "https://github.com/encode/httpx",
            "interval_seconds": 90,
            "notification_channels": [
                {
                    "name": "team-mail",
                    "channel_type": "smtp",
                    "target": "not-an-email",
                },
            ],
        },
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["code"] == 422
    assert payload["success"] is False


async def test_update_subscription_changes_interval_and_notification_channel(client):
    create_response = await client.post(
        "/api/subscriptions",
        json={
            "repository_url": "https://github.com/encode/httpx",
            "interval_seconds": 90,
            "notification_channels": [
                {
                    "channel_type": "smtp",
                    "target": "team@example.com",
                },
            ],
        },
    )
    subscription_id = create_response.json()["data"]["id"]

    response = await client.patch(
        f"/api/subscriptions/{subscription_id}",
        json={
            "interval_seconds": 3600,
            "notification_channels": [
                {
                    "channel_type": "wecom",
                    "target": "repo-alerts",
                },
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    updated = payload["data"]
    assert updated["repository_url"] == "https://github.com/encode/httpx"
    assert updated["interval_seconds"] == 3600
    assert updated["notification_channels"] == [
        {
            "id": 2,
            "name": "wecom-repo-alerts",
            "channel_type": "wecom",
            "target": "repo-alerts",
            "is_active": True,
        },
    ]


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


async def test_list_subscriptions_does_not_show_admin_data_to_new_user(anonymous_client):
    admin_create = await anonymous_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "123456"},
    )
    assert admin_create.status_code == 200
    await anonymous_client.post(
        "/api/subscriptions",
        json={
            "repository_url": "https://github.com/acme/admin-repo",
            "interval_seconds": 120,
        },
    )
    register = await anonymous_client.post(
        "/api/auth/register",
        json={"username": "alice_10", "password": "secret1"},
    )
    assert register.status_code == 201
    login = await anonymous_client.post(
        "/api/auth/login",
        json={"username": "alice_10", "password": "secret1"},
    )
    assert login.status_code == 200

    response = await anonymous_client.get("/api/subscriptions")

    assert response.status_code == 200
    assert response.json()["data"] == []


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


async def test_create_subscription_persists_multiple_notification_channel_bindings():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        subscription = await create_subscription(
            session,
            SubscriptionCreate(
                repository_url="https://github.com/acme/sentinel",
                interval_seconds=60,
                notification_channels=[
                    {
                        "name": "team-mail",
                        "channel_type": "smtp",
                        "target": "team@example.com",
                    },
                    {
                        "name": "repo-alerts",
                        "channel_type": "wecom",
                        "target": "repo-alerts",
                    },
                    {
                        "name": "release-bot",
                        "channel_type": "webhook",
                        "target": "release-bot",
                    },
                ],
            ),
        )
        channels = list((await session.execute(select(NotificationChannel))).scalars().all())
        bindings = list(
            (await session.execute(select(SubscriptionNotificationChannel))).scalars().all(),
        )

    assert subscription.id is not None
    assert [(channel.name, channel.channel_type, channel.target) for channel in channels] == [
        ("team-mail", "smtp", "team@example.com"),
        ("repo-alerts", "wecom", "repo-alerts"),
        ("release-bot", "webhook", "release-bot"),
    ]
    assert [binding.subscription_id for binding in bindings] == [subscription.id] * 3
    assert [binding.notification_channel_id for binding in bindings] == [
        channel.id for channel in channels
    ]

    await engine.dispose()


async def test_create_subscription_scopes_channel_names_to_repository_subscription():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        first = await create_subscription(
            session,
            SubscriptionCreate(
                repository_url="https://github.com/acme/sentinel",
                interval_seconds=60,
                notification_channels=[
                    {
                        "name": "team-mail",
                        "channel_type": "smtp",
                        "target": "sentinel@example.com",
                    },
                ],
            ),
        )
        second = await create_subscription(
            session,
            SubscriptionCreate(
                repository_url="https://github.com/acme/frontend",
                interval_seconds=60,
                notification_channels=[
                    {
                        "name": "team-mail",
                        "channel_type": "smtp",
                        "target": "frontend@example.com",
                    },
                ],
            ),
        )
        channels = list(
            (
                await session.execute(
                    select(NotificationChannel).order_by(NotificationChannel.id),
                )
            )
            .scalars()
            .all(),
        )
        bindings = list(
            (
                await session.execute(
                    select(SubscriptionNotificationChannel).order_by(
                        SubscriptionNotificationChannel.id,
                    ),
                )
            )
            .scalars()
            .all(),
        )

    assert [(channel.name, channel.target) for channel in channels] == [
        ("team-mail", "sentinel@example.com"),
        ("team-mail", "frontend@example.com"),
    ]
    assert [(binding.subscription_id, binding.notification_channel_id) for binding in bindings] == [
        (first.id, channels[0].id),
        (second.id, channels[1].id),
    ]

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


async def test_delete_subscription_removes_related_events_reports_notification_jobs_and_bindings():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        subscription = await create_subscription(
            session,
            SubscriptionCreate(
                repository_url="https://github.com/acme/sentinel",
                interval_seconds=60,
                notification_channels=[
                    {
                        "name": "team-mail",
                        "channel_type": "smtp",
                        "target": "team@example.com",
                    },
                ],
            ),
        )
        channel = list((await session.execute(select(NotificationChannel))).scalars().all())[0]
        event = RepositoryEvent(
            subscription_id=subscription.id,
            event_type="PushEvent",
            external_id="event-1",
            title="Update dashboard",
            url="https://github.com/acme/sentinel/commit/1",
            occurred_at=subscription.created_at,
        )
        report = Report(
            subscription_id=subscription.id,
            name="acme_sentinel_2026-06-03",
            content_markdown="# report",
            generated_at=subscription.created_at,
        )
        session.add_all([event, report])
        await session.commit()
        await session.refresh(report)
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

        await delete_subscription(session, subscription.id)

        remaining_subscriptions = list((await session.execute(select(Subscription))).scalars().all())
        remaining_events = list((await session.execute(select(RepositoryEvent))).scalars().all())
        remaining_reports = list((await session.execute(select(Report))).scalars().all())
        remaining_jobs = list((await session.execute(select(NotificationJob))).scalars().all())
        remaining_bindings = list(
            (await session.execute(select(SubscriptionNotificationChannel))).scalars().all(),
        )
        remaining_channels = list((await session.execute(select(NotificationChannel))).scalars().all())

    assert remaining_subscriptions == []
    assert remaining_events == []
    assert remaining_reports == []
    assert remaining_jobs == []
    assert remaining_bindings == []
    assert remaining_channels == []

    await engine.dispose()
