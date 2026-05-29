"""
Sentinel 代理服务，负责运行订阅代理，获取 GitHub 活动、渲染报告、发送通知。
定义核心编排服务 `SentinelAgent` 和运行结果 `SentinelRunResult`。该服务负责按订阅拉取仓库活动、存储新事件、生成报告，并在配置通知通道时发送通知。
"""
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.db.models import Subscription
from app.repositories.events import store_new_repository_events
from app.repositories.reports import create_report
from app.services.github_client import GitHubActivity, GitHubClient
from app.services.notifications import NotificationSender
from app.services.reporting import ReportRenderer


@dataclass(frozen=True)
class SentinelRunResult:
    """描述一次订阅运行后的抓取、入库、报告和通知结果。"""

    subscription_id: int
    fetched_events: int
    stored_events: int
    report_id: int | None
    notification_sent: bool


class SentinelAgent:
    """Sentinel 核心编排服务，负责按订阅抓取动态并生成报告。"""

    def __init__(
        self,
        github_client: GitHubClient,
        report_renderer: ReportRenderer,
        notification_sender: NotificationSender,
    ) -> None:
        """注入抓取、报告渲染和通知发送依赖，便于测试和后续替换实现。"""
        self._github_client = github_client
        self._report_renderer = report_renderer
        self._notification_sender = notification_sender

    async def run_subscription(
        self,
        session: AsyncSession,
        subscription_id: int,
    ) -> SentinelRunResult:
        """执行单个订阅：抓取仓库动态、幂等存储事件、生成报告并按需通知。"""
        subscription = await session.get(Subscription, subscription_id)
        if subscription is None:
            raise ApiError(
                status_code=404,
                code="subscription_not_found",
                message="订阅不存在。",
            )
        if not subscription.is_active:
            raise ApiError(
                status_code=409,
                code="subscription_inactive",
                message="订阅已停用。",
            )

        activities = await self._github_client.fetch_repository_activity(
            platform=subscription.platform,
            owner=subscription.owner,
            repo=subscription.repo,
            access_token_encrypted=subscription.access_token_encrypted or "",
            since=None,
        )
        stored_events = await store_new_repository_events(session, subscription.id, activities)

        report_id: int | None = None
        notification_sent = False
        if stored_events:
            digest_activities = [
                GitHubActivity(
                    external_id=event.external_id,
                    event_type=event.event_type,
                    title=event.title,
                    url=event.url,
                    occurred_at=event.occurred_at,
                )
                for event in stored_events
            ]
            subject = f"{subscription.owner}/{subscription.repo} 仓库更新摘要（{subscription.interval_seconds} 秒订阅）"
            summary = self._report_renderer.render_digest(
                subscription.owner,
                subscription.repo,
                digest_activities,
            )
            report = await create_report(session, subscription.id, subject, summary)
            report_id = report.id
            await session.commit()

            if subscription.notification_channel:
                await self._notification_sender.send(subscription.notification_channel, subject, summary)
                notification_sent = True
        else:
            await session.commit()

        return SentinelRunResult(
            subscription_id=subscription.id,
            fetched_events=len(activities),
            stored_events=len(stored_events),
            report_id=report_id,
            notification_sent=notification_sent,
        )
