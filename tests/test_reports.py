from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import Report, Subscription
from app.db.session import get_session
from app.main import create_app


async def test_list_reports_filters_by_recent_seconds():
    """用户查看报告时，可以选择最近一段时间内生成的报告。"""
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
            interval_seconds=60,
        )
        session.add(subscription)
        await session.flush()
        session.add_all(
            [
                Report(
                    subscription_id=subscription.id,
                    title="最近报告",
                    summary="最近一小时内生成",
                    generated_at=datetime.now(timezone.utc) - timedelta(minutes=30),
                ),
                Report(
                    subscription_id=subscription.id,
                    title="历史报告",
                    summary="两天前生成",
                    generated_at=datetime.now(timezone.utc) - timedelta(days=2),
                ),
            ],
        )
        await session.commit()

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        """让本测试的 API 请求使用同一个内存数据库。"""
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/reports", params={"within_seconds": 3600})

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert [item["title"] for item in payload["data"]] == ["最近报告"]

    await engine.dispose()
