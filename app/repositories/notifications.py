"""通知通道绑定与通知任务仓储。"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import NotificationJob, Report, Subscription, SubscriptionNotificationChannel


async def create_notification_jobs_for_report(
    session: AsyncSession,
    subscription: Subscription,
    report: Report,
) -> list[NotificationJob]:
    """按订阅绑定的启用通道为报告创建待发送通知任务。"""
    result = await session.execute(
        select(SubscriptionNotificationChannel)
        .where(
            SubscriptionNotificationChannel.subscription_id == subscription.id,
            SubscriptionNotificationChannel.is_enabled.is_(True),
        )
        .order_by(SubscriptionNotificationChannel.id),
    )
    bindings = list(result.scalars().all())
    jobs: list[NotificationJob] = []
    for binding in bindings:
        dedupe_key = f"{report.id}:{binding.notification_channel_id}"
        existing_job = await _get_notification_job_by_dedupe_key(session, dedupe_key)
        if existing_job is not None:
            jobs.append(existing_job)
            continue

        job = NotificationJob(
            subscription_id=subscription.id,
            report_id=report.id,
            notification_channel_id=binding.notification_channel_id,
            subject=report.name,
            body_markdown=report.content_markdown,
            dedupe_key=dedupe_key,
        )
        session.add(job)
        jobs.append(job)

    await session.flush()
    return jobs


async def _get_notification_job_by_dedupe_key(
    session: AsyncSession,
    dedupe_key: str,
) -> NotificationJob | None:
    result = await session.execute(
        select(NotificationJob).where(NotificationJob.dedupe_key == dedupe_key),
    )
    return result.scalar_one_or_none()
