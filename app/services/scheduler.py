"""订阅定时调度器。"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.logging import get_logger
from app.db.models import Subscription


class SubscriptionRunner(Protocol):
    """调度器依赖的订阅执行协议。"""

    async def run_subscription(self, session: AsyncSession, subscription_id: int):
        """执行一次订阅抓取与报告生成。"""
        raise NotImplementedError


@dataclass(frozen=True)
class SchedulerRunResult:
    """描述一次调度扫描的执行结果。"""

    checked: int
    executed: int
    failed: int


class SubscriptionScheduler:
    """应用内轻量订阅调度器。"""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        sentinel_agent: SubscriptionRunner,
        tick_seconds: int = 30,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._sentinel_agent = sentinel_agent
        self._tick_seconds = tick_seconds
        self._now_provider = now_provider or _utc_now
        self._running_subscription_ids: set[int] = set()
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._logger = get_logger("scheduler")

    def start(self) -> None:
        """启动后台调度循环。"""
        if self._task is not None and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_loop())
        self._logger.info("订阅调度器已启动", extra={"duration_ms": self._tick_seconds * 1000})

    async def stop(self) -> None:
        """停止后台调度循环。"""
        self._stop_event.set()
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._logger.info("订阅调度器已停止")

    async def run_due_once(self, now: datetime | None = None) -> SchedulerRunResult:
        """扫描并执行一次当前到期的活跃订阅。"""
        scan_time = normalize_scheduler_datetime(now or self._now_provider())
        async with self._session_factory() as session:
            subscriptions = await self._list_active_subscriptions(session)
            checked = len(subscriptions)
            executed = 0
            failed = 0

            for subscription in subscriptions:
                if not self._is_due(subscription, scan_time):
                    continue
                if subscription.id in self._running_subscription_ids:
                    continue

                self._running_subscription_ids.add(subscription.id)
                try:
                    await self._sentinel_agent.run_subscription(session, subscription.id)
                    subscription.last_run_at = scan_time
                    subscription.next_run_at = scan_time + timedelta(
                        seconds=subscription.interval_seconds,
                    )
                    await session.commit()
                    executed += 1
                    self._logger.info(
                        "订阅定时任务执行成功",
                        extra={
                            "subscription_id": subscription.id,
                            "owner": subscription.owner,
                            "repo": subscription.repo,
                        },
                    )
                except Exception:
                    await session.rollback()
                    failed += 1
                    self._logger.exception(
                        "订阅定时任务执行失败",
                        extra={
                            "subscription_id": subscription.id,
                            "owner": subscription.owner,
                            "repo": subscription.repo,
                        },
                    )
                finally:
                    self._running_subscription_ids.discard(subscription.id)

            return SchedulerRunResult(checked=checked, executed=executed, failed=failed)

    async def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            await self.run_due_once()
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self._tick_seconds)
            except TimeoutError:
                continue

    async def _list_active_subscriptions(self, session: AsyncSession) -> list[Subscription]:
        result = await session.execute(
            select(Subscription)
            .where(Subscription.is_active.is_(True))
            .order_by(Subscription.id),
        )
        return list(result.scalars().all())

    def _is_due(self, subscription: Subscription, now: datetime) -> bool:
        if subscription.next_run_at is None:
            return True
        return normalize_scheduler_datetime(subscription.next_run_at) <= now


def _utc_now() -> datetime:
    return datetime.now(UTC)


def normalize_scheduler_datetime(value: datetime) -> datetime:
    """把调度时间归一为 UTC，兼容 SQLite 读回的无时区时间。"""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
