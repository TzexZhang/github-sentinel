"""Sentinel 核心编排服务。"""

from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.core.logging import get_logger
from app.db.models import Report, RepositoryEvent, Subscription
from app.repositories.events import list_repository_events, store_new_repository_events
from app.repositories.reports import create_report
from app.services.github_client import GitHubActivity, GitHubClient
from app.services.llm import LLMClient, LLMError
from app.services.notifications import NotificationSender
from app.services.reporting import ReportRenderer, build_repository_report_prompt
from app.services.time_utils import (
    local_date_range_to_utc_bounds,
    normalize_event_datetime,
    report_now,
)

logger = get_logger("sentinel")


@dataclass(frozen=True)
class SentinelRunResult:
    """描述一次订阅运行及其报告生成结果。"""

    subscription_id: int
    fetched_events: int
    stored_events: int
    report_id: int | None
    notification_sent: bool


class SentinelAgent:
    """编排抓取、去重、报告生成和通知发送流程。"""

    def __init__(
        self,
        github_client: GitHubClient,
        report_renderer: ReportRenderer,
        notification_sender: NotificationSender,
        llm_client: LLMClient | None = None,
    ) -> None:
        self._github_client = github_client
        self._report_renderer = report_renderer
        self._notification_sender = notification_sender
        self._llm_client = llm_client

    async def run_subscription(
        self,
        session: AsyncSession,
        subscription_id: int,
    ) -> SentinelRunResult:
        """按订阅间隔作为时间窗口执行一次抓取并生成报告。"""
        subscription = await self._get_active_subscription(session, subscription_id)
        generated_at = report_now()
        occurred_before = normalize_event_datetime(generated_at)
        occurred_since = occurred_before - timedelta(seconds=subscription.interval_seconds)
        report_name = _build_daily_report_name(subscription.owner, subscription.repo, generated_at)
        result, report = await self._fetch_store_and_create_report(
            session=session,
            subscription=subscription,
            occurred_since=occurred_since,
            occurred_before=occurred_before,
            generated_at=generated_at,
            report_name=report_name,
            period_start_date=None,
            period_end_date=None,
        )
        logger.info(
            "订阅抓取与报告生成完成",
            extra={
                "subscription_id": result.subscription_id,
                "owner": subscription.owner,
                "repo": subscription.repo,
                "fetched_events": result.fetched_events,
                "stored_events": result.stored_events,
                "report_id": result.report_id,
            },
        )

        notification_sent = False
        if subscription.notification_channel:
            await self._notification_sender.send(
                subscription.notification_channel,
                report.name,
                report.content_markdown,
            )
            notification_sent = True

        return SentinelRunResult(
            subscription_id=result.subscription_id,
            fetched_events=result.fetched_events,
            stored_events=result.stored_events,
            report_id=result.report_id,
            notification_sent=notification_sent,
        )

    async def generate_report_for_date_range(
        self,
        session: AsyncSession,
        subscription_id: int,
        start_date: date,
        end_date: date,
    ) -> tuple[SentinelRunResult, Report]:
        """按用户选择的日期范围抓取最新事件、更新事件表，并生成 Markdown 报告。"""
        subscription = await self._get_active_subscription(session, subscription_id)
        generated_at = report_now()
        occurred_since, occurred_before = local_date_range_to_utc_bounds(start_date, end_date)
        report_name = _build_date_range_report_name(
            subscription.owner,
            subscription.repo,
            start_date,
            end_date,
        )
        return await self._fetch_store_and_create_report(
            session=session,
            subscription=subscription,
            occurred_since=occurred_since,
            occurred_before=occurred_before,
            generated_at=generated_at,
            report_name=report_name,
            period_start_date=start_date,
            period_end_date=end_date,
        )

    async def _fetch_store_and_create_report(
        self,
        session: AsyncSession,
        subscription: Subscription,
        occurred_since: datetime,
        occurred_before: datetime,
        generated_at: datetime,
        report_name: str,
        period_start_date: date | None,
        period_end_date: date | None,
    ) -> tuple[SentinelRunResult, Report]:
        activities = await self._github_client.fetch_repository_activity(
            platform=subscription.platform,
            owner=subscription.owner,
            repo=subscription.repo,
            access_token_encrypted=subscription.access_token_encrypted or "",
            since=occurred_since,
        )
        activities = [
            replace(activity, occurred_at=normalize_event_datetime(activity.occurred_at))
            for activity in activities
        ]
        activities = [
            activity
            for activity in activities
            if occurred_since <= activity.occurred_at < occurred_before
        ]
        stored_events = await store_new_repository_events(session, subscription.id, activities)
        events_for_report = await list_repository_events(
            session,
            subscription.id,
            occurred_since,
            occurred_before,
        )
        digest_activities = [_activity_from_event(event) for event in events_for_report]
        content_markdown = await self._render_report_markdown(
            subscription=subscription,
            activities=digest_activities,
            occurred_since=occurred_since,
            occurred_before=occurred_before,
        )
        report = await create_report(
            session,
            subscription.id,
            report_name,
            content_markdown,
            generated_at,
            period_start_date=period_start_date,
            period_end_date=period_end_date,
        )
        await session.commit()
        return (
            SentinelRunResult(
                subscription_id=subscription.id,
                fetched_events=len(activities),
                stored_events=len(stored_events),
                report_id=report.id,
                notification_sent=False,
            ),
            report,
        )

    async def _render_report_markdown(
        self,
        subscription: Subscription,
        activities: list[GitHubActivity],
        occurred_since: datetime,
        occurred_before: datetime,
    ) -> str:
        if self._llm_client is not None:
            prompt = build_repository_report_prompt(
                subscription.owner,
                subscription.repo,
                activities,
                occurred_since,
                occurred_before,
            )
            try:
                content = await self._llm_client.generate_markdown(prompt)
                logger.info(
                    "LLM 报告生成成功",
                    extra={"subscription_id": subscription.id},
                )
                return content
            except LLMError:
                logger.exception(
                    "LLM 报告生成失败，使用本地 Markdown 模板兜底",
                    extra={"subscription_id": subscription.id},
                )

        return self._report_renderer.render_digest(
            subscription.owner,
            subscription.repo,
            activities,
        )

    async def _get_active_subscription(
        self,
        session: AsyncSession,
        subscription_id: int,
    ) -> Subscription:
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
        return subscription


def _activity_from_event(event: RepositoryEvent) -> GitHubActivity:
    return GitHubActivity(
        external_id=event.external_id,
        event_type=event.event_type,
        title=event.title,
        url=event.url,
        occurred_at=event.occurred_at,
    )


def _safe_report_part(value: str) -> str:
    return value.replace("/", "_").replace(" ", "_")


def _build_daily_report_name(owner: str, repo: str, generated_at: datetime) -> str:
    return f"{_safe_report_part(owner)}_{_safe_report_part(repo)}_{generated_at.date().isoformat()}"


def _build_date_range_report_name(owner: str, repo: str, start_date: date, end_date: date) -> str:
    return (
        f"{_safe_report_part(owner)}_{_safe_report_part(repo)}_"
        f"{start_date.isoformat()}_{end_date.isoformat()}"
    )
