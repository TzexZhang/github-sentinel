from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.migrations import (
    ensure_notification_channel_table,
    ensure_notification_job_table,
    ensure_subscription_columns,
)


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


async def test_notification_channel_migration_removes_global_name_unique_constraint():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)

    async with engine.begin() as connection:
        await connection.execute(
            text(
                """
                CREATE TABLE notification_channels (
                    id INTEGER NOT NULL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL UNIQUE,
                    channel_type VARCHAR(30) NOT NULL,
                    target VARCHAR(500) NOT NULL,
                    is_active BOOLEAN NOT NULL,
                    created_at DATETIME
                )
                """,
            ),
        )
        await connection.execute(
            text(
                """
                INSERT INTO notification_channels (
                    id,
                    name,
                    channel_type,
                    target,
                    is_active,
                    created_at
                )
                VALUES (1, 'team-mail', 'smtp', 'sentinel@example.com', 1, CURRENT_TIMESTAMP)
                """,
            ),
        )

        await ensure_notification_channel_table(connection)

        await connection.execute(
            text(
                """
                INSERT INTO notification_channels (
                    id,
                    name,
                    channel_type,
                    target,
                    is_active,
                    created_at
                )
                VALUES (2, 'team-mail', 'smtp', 'frontend@example.com', 1, CURRENT_TIMESTAMP)
                """,
            ),
        )
        rows_result = await connection.execute(
            text("SELECT name, target FROM notification_channels ORDER BY id"),
        )

    assert rows_result.fetchall() == [
        ("team-mail", "sentinel@example.com"),
        ("team-mail", "frontend@example.com"),
    ]

    await engine.dispose()


async def test_notification_job_migration_removes_body_markdown_and_adds_pending_index():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)

    async with engine.begin() as connection:
        await connection.execute(
            text(
                """
                CREATE TABLE notification_jobs (
                    id INTEGER NOT NULL PRIMARY KEY,
                    subscription_id INTEGER NOT NULL,
                    report_id INTEGER NOT NULL,
                    notification_channel_id INTEGER NOT NULL,
                    status VARCHAR(20) NOT NULL,
                    subject VARCHAR(300) NOT NULL,
                    body_markdown TEXT NOT NULL,
                    retry_count INTEGER NOT NULL,
                    next_attempt_at DATETIME,
                    dedupe_key VARCHAR(100) NOT NULL,
                    last_error TEXT,
                    created_at DATETIME,
                    sent_at DATETIME
                )
                """,
            ),
        )
        await connection.execute(
            text(
                """
                INSERT INTO notification_jobs (
                    id,
                    subscription_id,
                    report_id,
                    notification_channel_id,
                    status,
                    subject,
                    body_markdown,
                    retry_count,
                    next_attempt_at,
                    dedupe_key,
                    created_at
                )
                VALUES (
                    1,
                    10,
                    20,
                    30,
                    'pending',
                    'report',
                    '# duplicated body',
                    0,
                    CURRENT_TIMESTAMP,
                    '20:30',
                    CURRENT_TIMESTAMP
                )
                """,
            ),
        )

        await ensure_notification_job_table(connection)

        columns_result = await connection.execute(text("PRAGMA table_info(notification_jobs)"))
        columns = {row[1] for row in columns_result.fetchall()}
        index_result = await connection.execute(text("PRAGMA index_list(notification_jobs)"))
        indexes = {row[1] for row in index_result.fetchall()}
        row_result = await connection.execute(
            text("SELECT id, subscription_id, report_id, subject, dedupe_key FROM notification_jobs"),
        )

    assert "body_markdown" not in columns
    assert "ix_notification_jobs_status_next_attempt_at" in indexes
    assert row_result.fetchone() == (1, 10, 20, "report", "20:30")

    await engine.dispose()
