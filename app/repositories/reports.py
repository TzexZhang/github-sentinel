"""报告持久化辅助函数。"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Report


async def create_report(
    session: AsyncSession,
    subscription_id: int,
    name: str,
    content_markdown: str,
    generated_at: datetime,
) -> Report:
    """创建 Markdown 报告记录，并刷新自增主键。"""
    report = Report(
        subscription_id=subscription_id,
        name=name,
        content_markdown=content_markdown,
        generated_at=generated_at,
    )
    session.add(report)
    await session.flush()
    await session.refresh(report)
    return report


async def list_reports(
    session: AsyncSession,
    subscription_id: int | None = None,
    generated_since: datetime | None = None,
) -> list[Report]:
    """按时间倒序查询报告，可按订阅和生成时间过滤。"""
    statement = select(Report)
    if subscription_id is not None:
        statement = statement.where(Report.subscription_id == subscription_id)
    if generated_since is not None:
        statement = statement.where(Report.generated_at >= generated_since)
    result = await session.execute(statement.order_by(Report.generated_at.desc(), Report.id.desc()))
    return list(result.scalars().all())
