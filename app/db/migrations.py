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


def _requires_subscription_rebuild(existing_columns: set[str]) -> bool:
    """判断现有 subscriptions 表列集合是否需要重建。"""
    desired_columns = {
        "id",
        "platform",
        "owner",
        "repo",
        "repository_url",
        "interval_seconds",
        "access_token_encrypted",
        "notification_channel",
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
                platform VARCHAR(20) NOT NULL DEFAULT 'github',
                owner VARCHAR(100) NOT NULL,
                repo VARCHAR(100) NOT NULL,
                repository_url VARCHAR(500) NOT NULL,
                interval_seconds INTEGER NOT NULL DEFAULT 86400,
                access_token_encrypted TEXT,
                notification_channel VARCHAR(200),
                is_active BOOLEAN NOT NULL DEFAULT 1,
                last_run_at DATETIME,
                next_run_at DATETIME,
                created_at DATETIME,
                updated_at DATETIME,
                CONSTRAINT uq_subscription_repo UNIQUE (platform, owner, repo)
            )
            """,
        ),
    )
    await connection.execute(text("CREATE INDEX ix_subscriptions_platform ON subscriptions (platform)"))
    await connection.execute(text("CREATE INDEX ix_subscriptions_owner ON subscriptions (owner)"))
    await connection.execute(text("CREATE INDEX ix_subscriptions_repo ON subscriptions (repo)"))

    if {"id", "owner", "repo"}.issubset(existing_columns):
        platform_expression = (
            "COALESCE(NULLIF(platform, ''), 'github')"
            if "platform" in existing_columns
            else "'github'"
        )
        repository_url_expression = _repository_url_expression(existing_columns)
        interval_expression = "interval_seconds" if "interval_seconds" in existing_columns else "86400"
        token_expression = (
            "access_token_encrypted" if "access_token_encrypted" in existing_columns else "NULL"
        )
        notification_expression = (
            "notification_channel" if "notification_channel" in existing_columns else "NULL"
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
                    platform,
                    owner,
                    repo,
                    repository_url,
                    interval_seconds,
                    access_token_encrypted,
                    notification_channel,
                    is_active,
                    last_run_at,
                    next_run_at,
                    created_at,
                    updated_at
                )
                SELECT
                    id,
                    {platform_expression},
                    owner,
                    repo,
                    {repository_url_expression},
                    {interval_expression},
                    {token_expression},
                    {notification_expression},
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
