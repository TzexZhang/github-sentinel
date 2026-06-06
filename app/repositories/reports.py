"""报告持久化辅助函数。"""

from datetime import date, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import NotificationJob, Report, Subscription


async def get_report_by_period(
    session: AsyncSession,
    subscription_id: int,
    period_start_date: date,
    period_end_date: date,
) -> Report | None:
    """查询指定订阅在同一日期范围内的已有报告。"""
    result = await session.execute(
        select(Report).where(
            Report.subscription_id == subscription_id,
            Report.period_start_date == period_start_date,
            Report.period_end_date == period_end_date,
        ),
    )
    return result.scalar_one_or_none()


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
        report = await get_report_by_period(
            session,
            subscription_id,
            period_start_date,
            period_end_date,
        )

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
    user_id: int | None = None,
    generated_since: datetime | None = None,
    generated_before: datetime | None = None,
) -> list[Report]:
    """按时间倒序查询报告，可按订阅和生成时间过滤。"""
    statement = select(Report).options(selectinload(Report.subscription))
    if user_id is not None:
        statement = statement.join(Subscription).where(Subscription.user_id == user_id)
    if subscription_id is not None:
        statement = statement.where(Report.subscription_id == subscription_id)
    if generated_since is not None:
        statement = statement.where(Report.generated_at >= generated_since)
    if generated_before is not None:
        statement = statement.where(Report.generated_at < generated_before)
    result = await session.execute(statement.order_by(Report.generated_at.desc(), Report.id.desc()))
    return list(result.scalars().all())


async def batch_delete_reports(
    session: AsyncSession,
    report_ids: list[int],
    user_id: int,
) -> tuple[int, list[int]]:
    """物理删除当前用户拥有的报告及其通知任务。"""
    unique_ids = list(dict.fromkeys(report_ids))
    result = await session.execute(
        select(Report.id)
        .join(Subscription)
        .where(Report.id.in_(unique_ids), Subscription.user_id == user_id),
    )
    owned_ids = set(result.scalars().all())
    if owned_ids:
        await session.execute(delete(NotificationJob).where(NotificationJob.report_id.in_(owned_ids)))
        await session.execute(delete(Report).where(Report.id.in_(owned_ids)))
        await session.commit()
    not_found_ids = [report_id for report_id in unique_ids if report_id not in owned_ids]
    return len(owned_ids), not_found_ids
