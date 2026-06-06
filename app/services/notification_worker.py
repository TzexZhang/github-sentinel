"""应用内通知任务 Worker。"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.db.models import NotificationChannel, NotificationJob
from app.services.notifications import NotificationDeliveryError


class NotificationJobSender(Protocol):
    """通知 Worker 依赖的发送协议。"""

    async def send(self, channel: NotificationChannel, subject: str, body: str) -> None:
        """发送一条通知任务。"""
        raise NotImplementedError


@dataclass(frozen=True)
class NotificationWorkerRunResult:
    """一次通知任务扫描的结果。"""

    checked: int
    sent: int
    failed: int


class NotificationWorker:
    """扫描并投递 `notification_jobs` 中的待发送任务。"""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        notification_sender: NotificationJobSender,
        tick_seconds: int = 30,
        batch_size: int = 50,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._notification_sender = notification_sender
        self._tick_seconds = tick_seconds
        self._batch_size = batch_size
        self._now_provider = now_provider or _utc_now
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._logger = get_logger("notification_worker")

    def start(self) -> None:
        """启动应用内通知 Worker 循环。"""
        if self._task is not None and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_loop())
        self._logger.info("通知 Worker 已启动", extra={"duration_ms": self._tick_seconds * 1000})

    async def stop(self) -> None:
        """停止应用内通知 Worker 循环。"""
        self._stop_event.set()
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._logger.info("通知 Worker 已停止")

    async def run_pending_once(self) -> NotificationWorkerRunResult:
        """扫描并投递当前待发送通知任务。"""
        now = self._now_provider()
        async with self._session_factory() as session:
            jobs = await self._list_pending_jobs(session, now)
            sent = 0
            failed = 0
            for job in jobs:
                try:
                    job.status = "sending"
                    await session.commit()
                    await self._notification_sender.send(
                        job.notification_channel,
                        job.subject,
                        job.report.content_markdown,
                    )
                    job.status = "sent"
                    job.sent_at = now
                    await session.commit()
                    sent += 1
                except NotificationDeliveryError as exc:
                    await session.rollback()
                    job.status = "failed"
                    job.retry_count += 1
                    job.last_error = str(exc)
                    await session.commit()
                    failed += 1
                    self._logger.warning(
                        "通知任务发送失败",
                        extra={
                            "notification_job_id": job.id,
                            "notification_channel_id": job.notification_channel_id,
                        },
                    )
            return NotificationWorkerRunResult(checked=len(jobs), sent=sent, failed=failed)

    async def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            await self.run_pending_once()
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self._tick_seconds)
            except TimeoutError:
                continue

    async def _list_pending_jobs(
        self,
        session: AsyncSession,
        now: datetime,
    ) -> list[NotificationJob]:
        result = await session.execute(
            select(NotificationJob)
            .options(
                selectinload(NotificationJob.notification_channel),
                selectinload(NotificationJob.report),
            )
            .where(
                NotificationJob.status == "pending",
                NotificationJob.next_attempt_at <= now,
            )
            .order_by(NotificationJob.id)
            .limit(self._batch_size),
        )
        return list(result.scalars().all())


def _utc_now() -> datetime:
    return datetime.now(UTC)
