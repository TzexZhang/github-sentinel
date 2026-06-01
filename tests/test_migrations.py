from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.migrations import ensure_subscription_columns


async def test_subscription_migration_drops_stale_legacy_table_before_rebuild():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)

    async with engine.begin() as connection:
        await connection.execute(
            text(
                """
                CREATE TABLE subscriptions (
                    id INTEGER NOT NULL PRIMARY KEY,
                    owner VARCHAR(100) NOT NULL,
                    repo VARCHAR(100) NOT NULL
                )
                """,
            ),
        )
        await connection.execute(
            text(
                """
                INSERT INTO subscriptions (id, owner, repo)
                VALUES (1, 'acme', 'sentinel')
                """,
            ),
        )
        await connection.execute(
            text(
                """
                CREATE TABLE subscriptions_legacy (
                    id INTEGER NOT NULL PRIMARY KEY,
                    owner VARCHAR(100) NOT NULL,
                    repo VARCHAR(100) NOT NULL
                )
                """,
            ),
        )

        await ensure_subscription_columns(connection)

        columns_result = await connection.execute(text("PRAGMA table_info(subscriptions)"))
        columns = {row[1] for row in columns_result.fetchall()}
        legacy_result = await connection.execute(
            text(
                """
                SELECT name FROM sqlite_master
                WHERE type = 'table' AND name = 'subscriptions_legacy'
                """,
            ),
        )
        data_result = await connection.execute(
            text("SELECT platform, owner, repo, repository_url FROM subscriptions WHERE id = 1"),
        )

    assert {"last_run_at", "next_run_at"}.issubset(columns)
    assert legacy_result.fetchone() is None
    assert data_result.fetchone() == (
        "github",
        "acme",
        "sentinel",
        "https://github.com/acme/sentinel",
    )

    await engine.dispose()
