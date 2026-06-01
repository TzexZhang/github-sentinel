"""报告持久化辅助函数。"""

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Report


async def create_report(
    session: AsyncSession,
    subscription_id: int,
    name: str,
    content_markdown: str,
    generated_at: datetime,
    period_start_date: date | None = None,
    period_end_date: date | None = None,
) -> Report:
    """创建或覆盖 Markdown 报告记录，并刷新自增主键。"""
    report = None
    if period_start_date is not None and period_end_date is not None:
        result = await session.execute(
            select(Report).where(
                Report.subscription_id == subscription_id,
                Report.period_start_date == period_start_date,
                Report.period_end_date == period_end_date,
            ),
        )
        report = result.scalar_one_or_none()

    if report is None:
        report = Report(
            subscription_id=subscription_id,
            name=name,
            content_markdown=content_markdown,
            generated_at=generated_at,
            period_start_date=period_start_date,
            period_end_date=period_end_date,
        )
        session.add(report)
    else:
        report.name = name
        report.content_markdown = content_markdown
        report.generated_at = generated_at
        report.period_start_date = period_start_date
        report.period_end_date = period_end_date
    await session.flush()
    await session.refresh(report)
    return report


async def list_reports(
    session: AsyncSession,
    subscription_id: int | None = None,
    generated_since: datetime | None = None,
    generated_before: datetime | None = None,
) -> list[Report]:
    """按时间倒序查询报告，可按订阅和生成时间过滤。"""
    statement = select(Report).options(selectinload(Report.subscription))
    if subscription_id is not None:
        statement = statement.where(Report.subscription_id == subscription_id)
    if generated_since is not None:
        statement = statement.where(Report.generated_at >= generated_since)
    if generated_before is not None:
        statement = statement.where(Report.generated_at < generated_before)
    result = await session.execute(statement.order_by(Report.generated_at.desc(), Report.id.desc()))
    return list(result.scalars().all())
