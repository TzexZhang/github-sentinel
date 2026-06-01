from collections.abc import AsyncIterator
from datetime import datetime, timezone
from datetime import date

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import Report, Subscription
from app.db.session import get_session
from app.main import create_app


async def test_list_subscription_reports_returns_selected_repository_markdown_reports():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        first = Subscription(
            platform="github",
            owner="acme",
            repo="sentinel",
            repository_url="https://github.com/acme/sentinel",
            interval_seconds=60,
        )
        second = Subscription(
            platform="github",
            owner="acme",
            repo="other",
            repository_url="https://github.com/acme/other",
            interval_seconds=60,
        )
        session.add_all([first, second])
        await session.flush()
        session.add_all(
            [
                Report(
                    subscription_id=first.id,
                    name="acme_sentinel_2026-05-30",
                    content_markdown="# sentinel",
                    generated_at=datetime(2026, 5, 30, tzinfo=timezone.utc),
                    period_start_date=date(2026, 5, 29),
                    period_end_date=date(2026, 5, 30),
                ),
                Report(
                    subscription_id=second.id,
                    name="acme_other_2026-05-30",
                    content_markdown="# other",
                    generated_at=datetime(2026, 5, 30, tzinfo=timezone.utc),
                ),
            ],
        )
        await session.commit()
        first_id = first.id

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(f"/api/subscriptions/{first_id}/reports")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"] == [
        {
            "id": 1,
            "subscription_id": first_id,
            "name": "acme_sentinel_2026-05-30",
            "generated_at": "2026-05-30 00:00:00",
            "period_start_date": "2026-05-29",
            "period_end_date": "2026-05-30",
            "content_markdown": "# sentinel",
        },
    ]

    await engine.dispose()
