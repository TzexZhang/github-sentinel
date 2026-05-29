"""
报告存储模块，负责存储和查询报告。
"""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Report


async def create_report(
    session: AsyncSession,
    subscription_id: int,
    title: str,
    summary: str,
) -> Report:
    """创建一条仓库报告记录并刷新自增主键。"""
    report = Report(subscription_id=subscription_id, title=title, summary=summary)
    session.add(report)
    await session.flush()
    await session.refresh(report)
    return report


async def list_reports(session: AsyncSession, generated_since: datetime | None = None) -> list[Report]:
    """按生成时间倒序查询报告列表，可按最早生成时间过滤。"""
    statement = select(Report)
    if generated_since is not None:
        statement = statement.where(Report.generated_at >= generated_since)
    result = await session.execute(statement.order_by(Report.generated_at.desc(), Report.id.desc()))
    return list(result.scalars().all())
