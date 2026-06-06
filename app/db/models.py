"""
数据库模型模块，负责定义数据库表结构。
定义数据库 ORM 模型：订阅、仓库事件、报告、通知通道、订阅通道绑定和通知任务。
"""
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utc_now() -> datetime:
    """返回当前 UTC 时间，供数据库时间字段默认值使用。"""
    # 数据库存储统一使用 UTC 时间，避免日报/周报跨时区计算混乱。
    return datetime.now(timezone.utc)


class Subscription(Base):
    """用户订阅的 GitHub/Gitee 仓库配置。"""

    # 用户订阅的代码托管仓库，同一个 platform/owner/repo 只允许订阅一次。
    __tablename__ = "subscriptions"
    __table_args__ = (
        UniqueConstraint("user_id", "platform", "owner", "repo", name="uq_subscription_user_repo"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, default=1, index=True)
    platform: Mapped[str] = mapped_column(String(20), nullable=False, default="github", index=True)
    owner: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    repo: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    repository_url: Mapped[str] = mapped_column(String(500), nullable=False)
    interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=86_400)
    access_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )

    @property
    def token_configured(self) -> bool:
        """标识当前订阅是否已配置加密访问令牌。"""
        return self.access_token_encrypted is not None

    notification_channels: Mapped[list["NotificationChannel"]] = relationship(
        secondary="subscription_notification_channels",
        lazy="selectin",
        overlaps="notification_channel,subscription",
    )
    user: Mapped["User"] = relationship()


class User(Base):
    """本地仪表盘和 API 登录账号。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(300), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )


class UserSession(Base):
    """服务端登录会话，仅持久化会话令牌哈希。"""

    __tablename__ = "user_sessions"
    __table_args__ = (UniqueConstraint("token_hash", name="uq_user_session_token_hash"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship()


class RepositoryEvent(Base):
    """从代码托管平台抓取并幂等保存的仓库动态。"""

    # 从 GitHub 拉取到的原始仓库动态，external_id 用于幂等去重。
    __tablename__ = "repository_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subscription_id: Mapped[int] = mapped_column(ForeignKey("subscriptions.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    external_id: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    subscription: Mapped[Subscription] = relationship()


class Report(Base):
    """由仓库动态聚合生成的摘要报告。"""

    # 由仓库动态聚合生成的日报或周报。
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subscription_id: Mapped[int] = mapped_column(ForeignKey("subscriptions.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    period_start_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    period_end_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)

    subscription: Mapped[Subscription] = relationship()


class NotificationChannel(Base):
    """通知通道基础配置，保存非敏感路由信息。"""

    # 通知通道仅保存基础路由信息；Token、签名密钥等敏感项必须来自环境变量。
    __tablename__ = "notification_channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, default=1, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    channel_type: Mapped[str] = mapped_column(String(30), nullable=False)
    target: Mapped[str] = mapped_column(String(500), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    user: Mapped[User] = relationship()


class SubscriptionNotificationChannel(Base):
    """订阅与通知通道的绑定关系。"""

    __tablename__ = "subscription_notification_channels"
    __table_args__ = (
        UniqueConstraint(
            "subscription_id",
            "notification_channel_id",
            name="uq_subscription_notification_channel",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subscription_id: Mapped[int] = mapped_column(ForeignKey("subscriptions.id"), nullable=False)
    notification_channel_id: Mapped[int] = mapped_column(
        ForeignKey("notification_channels.id"),
        nullable=False,
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    subscription: Mapped[Subscription] = relationship(overlaps="notification_channels")
    notification_channel: Mapped[NotificationChannel] = relationship(overlaps="notification_channels")


class NotificationJob(Base):
    """报告生成后等待投递的通知任务。"""

    __tablename__ = "notification_jobs"
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_notification_job_dedupe_key"),
        Index("ix_notification_jobs_status_next_attempt_at", "status", "next_attempt_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subscription_id: Mapped[int] = mapped_column(ForeignKey("subscriptions.id"), nullable=False)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id"), nullable=False)
    notification_channel_id: Mapped[int] = mapped_column(
        ForeignKey("notification_channels.id"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    dedupe_key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    subscription: Mapped[Subscription] = relationship()
    report: Mapped[Report] = relationship()
    notification_channel: Mapped[NotificationChannel] = relationship()
