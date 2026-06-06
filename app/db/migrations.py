from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


async def ensure_subscription_columns(connection: AsyncConnection) -> None:
    """确保 subscriptions 表符合当前订阅模型，旧结构会被平滑重建。"""
    result = await connection.execute(text("PRAGMA table_info(subscriptions)"))
    existing_columns = {row[1] for row in result.fetchall()}
    if not existing_columns:
        return

    if _requires_subscription_rebuild(existing_columns):
        await _rebuild_subscriptions_table(connection, existing_columns)


async def ensure_report_table(connection: AsyncConnection) -> None:
    """确保 reports 表符合当前 Markdown 报告结构。

    报告历史可以从仓库事件重新生成，因此当旧表结构不兼容时，
    会按当前约定清空并重建报告表。
    """
    result = await connection.execute(text("PRAGMA table_info(reports)"))
    existing_columns = {row[1] for row in result.fetchall()}
    if not existing_columns:
        return

    desired_columns = {
        "id",
        "subscription_id",
        "name",
        "content_markdown",
        "generated_at",
        "period_start_date",
        "period_end_date",
    }
    if existing_columns == desired_columns:
        return

    await connection.execute(text("DROP TABLE reports"))
    await connection.execute(
        text(
            """
            CREATE TABLE reports (
                id INTEGER NOT NULL PRIMARY KEY,
                subscription_id INTEGER NOT NULL,
                name VARCHAR(300) NOT NULL,
                content_markdown TEXT NOT NULL,
                generated_at DATETIME,
                period_start_date DATE,
                period_end_date DATE,
                FOREIGN KEY(subscription_id) REFERENCES subscriptions (id)
            )
            """,
        ),
    )
    await connection.execute(text("CREATE INDEX ix_reports_name ON reports (name)"))
    await connection.execute(text("CREATE INDEX ix_reports_period_start_date ON reports (period_start_date)"))
    await connection.execute(text("CREATE INDEX ix_reports_period_end_date ON reports (period_end_date)"))


async def ensure_repository_events_table(connection: AsyncConnection) -> None:
    """Ensure repository events are deduplicated per subscription, not globally."""
    result = await connection.execute(text("PRAGMA table_info(repository_events)"))
    existing_columns = {row[1] for row in result.fetchall()}
    if not existing_columns:
        return

    if existing_columns != {
        "id",
        "subscription_id",
        "event_type",
        "external_id",
        "title",
        "url",
        "occurred_at",
    }:
        await _rebuild_repository_events_table(connection, existing_columns)
        return

    index_result = await connection.execute(text("PRAGMA index_list(repository_events)"))
    has_subscription_external_unique = False
    has_global_external_unique = False
    for row in index_result.fetchall():
        index_name = row[1]
        is_unique = bool(row[2])
        if not is_unique:
            continue
        info_result = await connection.execute(text(f"PRAGMA index_info('{index_name}')"))
        indexed_columns = [info_row[2] for info_row in info_result.fetchall()]
        if indexed_columns == ["subscription_id", "external_id"]:
            has_subscription_external_unique = True
        if indexed_columns == ["external_id"]:
            has_global_external_unique = True

    if has_subscription_external_unique and not has_global_external_unique:
        return

    await _rebuild_repository_events_table(connection, existing_columns)


async def _rebuild_repository_events_table(
    connection: AsyncConnection,
    existing_columns: set[str],
) -> None:
    await connection.execute(text("DROP TABLE IF EXISTS repository_events_legacy"))
    await connection.execute(text("ALTER TABLE repository_events RENAME TO repository_events_legacy"))
    await connection.execute(text("DROP INDEX IF EXISTS ix_repository_events_external_id"))
    await connection.execute(text("DROP INDEX IF EXISTS ix_repository_events_subscription_id"))
    await connection.execute(
        text(
            """
            CREATE TABLE repository_events (
                id INTEGER NOT NULL PRIMARY KEY,
                subscription_id INTEGER NOT NULL,
                event_type VARCHAR(50) NOT NULL,
                external_id VARCHAR(200) NOT NULL,
                title VARCHAR(300) NOT NULL,
                url VARCHAR(500) NOT NULL,
                occurred_at DATETIME NOT NULL,
                CONSTRAINT uq_repository_event_subscription_external
                    UNIQUE (subscription_id, external_id),
                FOREIGN KEY(subscription_id) REFERENCES subscriptions (id)
            )
            """,
        ),
    )
    await connection.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS ix_repository_events_subscription_id
            ON repository_events (subscription_id)
            """,
        ),
    )

    required_columns = {"id", "subscription_id", "event_type", "external_id", "title", "url", "occurred_at"}
    if required_columns.issubset(existing_columns):
        await connection.execute(
            text(
                """
                INSERT OR IGNORE INTO repository_events (
                    id,
                    subscription_id,
                    event_type,
                    external_id,
                    title,
                    url,
                    occurred_at
                )
                SELECT
                    id,
                    subscription_id,
                    event_type,
                    external_id,
                    title,
                    url,
                    occurred_at
                FROM repository_events_legacy
                """,
            ),
        )

    await connection.execute(text("DROP TABLE repository_events_legacy"))


async def ensure_notification_channel_table(connection: AsyncConnection) -> None:
    """确保通知通道名称不再是全局唯一，通道归属由订阅绑定表表达。"""
    result = await connection.execute(text("PRAGMA table_info(notification_channels)"))
    existing_columns = {row[1] for row in result.fetchall()}
    if not existing_columns:
        return

    if "user_id" not in existing_columns:
        await connection.execute(
            text("ALTER TABLE notification_channels ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1"),
        )
        await connection.execute(
            text("CREATE INDEX IF NOT EXISTS ix_notification_channels_user_id ON notification_channels (user_id)"),
        )
        existing_columns.add("user_id")

    index_result = await connection.execute(text("PRAGMA index_list(notification_channels)"))
    has_unique_name_index = False
    for row in index_result.fetchall():
        index_name = row[1]
        is_unique = bool(row[2])
        if not is_unique:
            continue
        info_result = await connection.execute(text(f"PRAGMA index_info('{index_name}')"))
        indexed_columns = [info_row[2] for info_row in info_result.fetchall()]
        if indexed_columns == ["name"]:
            has_unique_name_index = True
            break

    if not has_unique_name_index:
        return

    await connection.execute(text("PRAGMA foreign_keys=OFF"))
    await connection.execute(text("ALTER TABLE notification_channels RENAME TO notification_channels_legacy"))
    await connection.execute(
        text(
            """
            CREATE TABLE notification_channels (
                id INTEGER NOT NULL PRIMARY KEY,
                user_id INTEGER NOT NULL DEFAULT 1,
                name VARCHAR(100) NOT NULL,
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
                user_id,
                name,
                channel_type,
                target,
                is_active,
                created_at
            )
            SELECT
                id,
                user_id,
                name,
                channel_type,
                target,
                is_active,
                created_at
            FROM notification_channels_legacy
            """,
        ),
    )
    await connection.execute(text("DROP TABLE notification_channels_legacy"))
    await connection.execute(text("PRAGMA foreign_keys=ON"))


async def ensure_notification_job_table(connection: AsyncConnection) -> None:
    """确保通知任务不复制报告正文，并具备 pending 扫描索引。"""
    result = await connection.execute(text("PRAGMA table_info(notification_jobs)"))
    existing_columns = {row[1] for row in result.fetchall()}
    if not existing_columns:
        return

    desired_columns = {
        "id",
        "subscription_id",
        "report_id",
        "notification_channel_id",
        "status",
        "subject",
        "retry_count",
        "next_attempt_at",
        "dedupe_key",
        "last_error",
        "created_at",
        "sent_at",
    }
    if existing_columns != desired_columns:
        await _rebuild_notification_jobs_table(connection, existing_columns)

    await connection.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS ix_notification_jobs_status_next_attempt_at
            ON notification_jobs (status, next_attempt_at)
            """,
        ),
    )


async def _rebuild_notification_jobs_table(
    connection: AsyncConnection,
    existing_columns: set[str],
) -> None:
    await connection.execute(text("DROP TABLE IF EXISTS notification_jobs_legacy"))
    await connection.execute(text("ALTER TABLE notification_jobs RENAME TO notification_jobs_legacy"))
    await connection.execute(text("DROP INDEX IF EXISTS ix_notification_jobs_status"))
    await connection.execute(text("DROP INDEX IF EXISTS ix_notification_jobs_next_attempt_at"))
    await connection.execute(text("DROP INDEX IF EXISTS ix_notification_jobs_status_next_attempt_at"))
    await connection.execute(text("DROP INDEX IF EXISTS ix_notification_jobs_dedupe_key"))
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
                retry_count INTEGER NOT NULL,
                next_attempt_at DATETIME,
                dedupe_key VARCHAR(100) NOT NULL,
                last_error TEXT,
                created_at DATETIME,
                sent_at DATETIME,
                CONSTRAINT uq_notification_job_dedupe_key UNIQUE (dedupe_key),
                FOREIGN KEY(subscription_id) REFERENCES subscriptions (id),
                FOREIGN KEY(report_id) REFERENCES reports (id),
                FOREIGN KEY(notification_channel_id) REFERENCES notification_channels (id)
            )
            """,
        ),
    )
    if {"id", "subscription_id", "report_id", "notification_channel_id", "subject", "dedupe_key"}.issubset(
        existing_columns,
    ):
        await connection.execute(
            text(
                f"""
                INSERT OR IGNORE INTO notification_jobs (
                    id,
                    subscription_id,
                    report_id,
                    notification_channel_id,
                    status,
                    subject,
                    retry_count,
                    next_attempt_at,
                    dedupe_key,
                    last_error,
                    created_at,
                    sent_at
                )
                SELECT
                    id,
                    subscription_id,
                    report_id,
                    notification_channel_id,
                    {_column_or_default(existing_columns, "status", "'pending'")},
                    subject,
                    {_column_or_default(existing_columns, "retry_count", "0")},
                    {_column_or_default(existing_columns, "next_attempt_at", "CURRENT_TIMESTAMP")},
                    dedupe_key,
                    {_column_or_default(existing_columns, "last_error", "NULL")},
                    {_column_or_default(existing_columns, "created_at", "CURRENT_TIMESTAMP")},
                    {_column_or_default(existing_columns, "sent_at", "NULL")}
                FROM notification_jobs_legacy
                """,
            ),
        )
    await connection.execute(text("DROP TABLE notification_jobs_legacy"))


def _column_or_default(existing_columns: set[str], column: str, default_expression: str) -> str:
    return column if column in existing_columns else default_expression


def _requires_subscription_rebuild(existing_columns: set[str]) -> bool:
    """判断现有 subscriptions 表列集合是否需要重建。"""
    desired_columns = {
        "id",
        "user_id",
        "platform",
        "owner",
        "repo",
        "repository_url",
        "interval_seconds",
        "access_token_encrypted",
        "is_active",
        "last_run_at",
        "next_run_at",
        "created_at",
        "updated_at",
    }
    return existing_columns != desired_columns


async def _rebuild_subscriptions_table(
    connection: AsyncConnection,
    existing_columns: set[str],
) -> None:
    """重建 subscriptions 表，并尽量迁移旧表中的可用订阅数据。"""
    await connection.execute(text("DROP TABLE IF EXISTS subscriptions_legacy"))
    await connection.execute(text("ALTER TABLE subscriptions RENAME TO subscriptions_legacy"))
    await connection.execute(text("DROP INDEX IF EXISTS ix_subscriptions_platform"))
    await connection.execute(text("DROP INDEX IF EXISTS ix_subscriptions_owner"))
    await connection.execute(text("DROP INDEX IF EXISTS ix_subscriptions_repo"))
    await connection.execute(
        text(
            """
            CREATE TABLE subscriptions (
                id INTEGER NOT NULL PRIMARY KEY,
                user_id INTEGER NOT NULL DEFAULT 1,
                platform VARCHAR(20) NOT NULL DEFAULT 'github',
                owner VARCHAR(100) NOT NULL,
                repo VARCHAR(100) NOT NULL,
                repository_url VARCHAR(500) NOT NULL,
                interval_seconds INTEGER NOT NULL DEFAULT 86400,
                access_token_encrypted TEXT,
                is_active BOOLEAN NOT NULL DEFAULT 1,
                last_run_at DATETIME,
                next_run_at DATETIME,
                created_at DATETIME,
                updated_at DATETIME,
                CONSTRAINT uq_subscription_user_repo UNIQUE (user_id, platform, owner, repo)
            )
            """,
        ),
    )
    await connection.execute(text("CREATE INDEX ix_subscriptions_platform ON subscriptions (platform)"))
    await connection.execute(text("CREATE INDEX ix_subscriptions_user_id ON subscriptions (user_id)"))
    await connection.execute(text("CREATE INDEX ix_subscriptions_owner ON subscriptions (owner)"))
    await connection.execute(text("CREATE INDEX ix_subscriptions_repo ON subscriptions (repo)"))

    if {"id", "owner", "repo"}.issubset(existing_columns):
        platform_expression = (
            "COALESCE(NULLIF(platform, ''), 'github')"
            if "platform" in existing_columns
            else "'github'"
        )
        user_id_expression = "user_id" if "user_id" in existing_columns else "1"
        repository_url_expression = _repository_url_expression(existing_columns)
        interval_expression = "interval_seconds" if "interval_seconds" in existing_columns else "86400"
        token_expression = (
            "access_token_encrypted" if "access_token_encrypted" in existing_columns else "NULL"
        )
        is_active_expression = "is_active" if "is_active" in existing_columns else "1"
        last_run_at_expression = "last_run_at" if "last_run_at" in existing_columns else "NULL"
        next_run_at_expression = "next_run_at" if "next_run_at" in existing_columns else "NULL"
        created_at_expression = "created_at" if "created_at" in existing_columns else "CURRENT_TIMESTAMP"
        updated_at_expression = "updated_at" if "updated_at" in existing_columns else "CURRENT_TIMESTAMP"

        await connection.execute(
            text(
                f"""
                INSERT OR IGNORE INTO subscriptions (
                    id,
                    user_id,
                    platform,
                    owner,
                    repo,
                    repository_url,
                    interval_seconds,
                    access_token_encrypted,
                    is_active,
                    last_run_at,
                    next_run_at,
                    created_at,
                    updated_at
                )
                SELECT
                    id,
                    {user_id_expression},
                    {platform_expression},
                    owner,
                    repo,
                    {repository_url_expression},
                    {interval_expression},
                    {token_expression},
                    {is_active_expression},
                    {last_run_at_expression},
                    {next_run_at_expression},
                    {created_at_expression},
                    {updated_at_expression}
                FROM subscriptions_legacy
                """,
            ),
        )

    await connection.execute(text("DROP TABLE subscriptions_legacy"))


def _repository_url_expression(existing_columns: set[str]) -> str:
    """生成 SQLite 表达式，用于从旧字段推导标准仓库地址。"""
    if "repository_url" in existing_columns:
        platform_expression = (
            "COALESCE(NULLIF(platform, ''), 'github')"
            if "platform" in existing_columns
            else "'github'"
        )
        return (
            "CASE WHEN repository_url IS NOT NULL AND repository_url != '' "
            "THEN repository_url "
            "ELSE 'https://' || "
            f"CASE {platform_expression} "
            "WHEN 'gitee' THEN 'gitee.com' "
            "ELSE 'github.com' END || '/' || owner || '/' || repo END"
        )
    platform_expression = (
        "COALESCE(NULLIF(platform, ''), 'github')"
        if "platform" in existing_columns
        else "'github'"
    )
    return (
        "'https://' || "
        f"CASE {platform_expression} "
        "WHEN 'gitee' THEN 'gitee.com' "
        "ELSE 'github.com' END || '/' || owner || '/' || repo"
    )
