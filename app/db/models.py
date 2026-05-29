"""
数据库模型模块，负责定义数据库表结构。
定义数据库 ORM 模型：`Subscription`、`RepositoryEvent`、`Report`、`NotificationChannel`。这些模型对应订阅、仓库事件、报告和通知通道
"""
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
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
    __table_args__ = (UniqueConstraint("platform", "owner", "repo", name="uq_subscription_repo"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    platform: Mapped[str] = mapped_column(String(20), nullable=False, default="github", index=True)
    owner: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    repo: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    repository_url: Mapped[str] = mapped_column(String(500), nullable=False)
    interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=86_400)
    access_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    notification_channel: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
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
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    subscription: Mapped[Subscription] = relationship()


class NotificationChannel(Base):
    """通知通道基础配置，预留给后续真实通知系统接入。"""

    # 通知通道仅保存基础路由信息；Token、签名密钥等敏感项必须来自环境变量。
    __tablename__ = "notification_channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    channel_type: Mapped[str] = mapped_column(String(30), nullable=False)
    target: Mapped[str] = mapped_column(String(500), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
