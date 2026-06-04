"""FastAPI 依赖注入别名。"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_session
from app.services.github_client import HttpRepositoryClient
from app.services.llm import build_llm_client
from app.services.notifications import (
    NotificationRouter,
    NullNotificationSender,
    SmtpNotificationSender,
    WeComNotificationSender,
    WebhookNotificationSender,
)
from app.services.reporting import MarkdownReportRenderer
from app.services.sentinel import SentinelAgent

DbSession = Annotated[AsyncSession, Depends(get_session)]


def build_sentinel_agent() -> SentinelAgent:
    """构建 Sentinel 核心编排服务。"""
    return SentinelAgent(
        github_client=HttpRepositoryClient(),
        report_renderer=MarkdownReportRenderer(),
        notification_sender=NullNotificationSender(),
        llm_client=build_llm_client(
            provider=settings.llm_provider,
            api_key=settings.resolved_llm_api_key,
            model=settings.llm_model,
            base_url=settings.llm_base_url,
            timeout=settings.llm_timeout_seconds,
        ),
    )


def build_notification_router() -> NotificationRouter:
    """根据配置构建真实通知通道路由器，供通知 Worker 复用。"""
    return NotificationRouter(
        smtp_sender=SmtpNotificationSender(
            host=settings.notification_smtp_host,
            port=settings.notification_smtp_port,
            username=settings.notification_smtp_username,
            password=settings.notification_smtp_password,
            from_email=settings.notification_smtp_from_email,
            use_tls=settings.notification_smtp_use_tls,
            use_ssl=settings.notification_smtp_use_ssl,
        ),
        wecom_sender=WeComNotificationSender(
            corp_id=settings.notification_wecom_corp_id,
            agent_id=settings.notification_wecom_agent_id,
            secret=settings.notification_wecom_secret,
            default_to_user=settings.notification_wecom_to_user,
            timeout_seconds=settings.notification_timeout_seconds,
        ),
        webhook_sender=WebhookNotificationSender(
            webhook_url=settings.notification_webhook_url,
            token=settings.notification_webhook_token,
            timeout_seconds=settings.notification_timeout_seconds,
        ),
    )


async def get_sentinel_agent() -> SentinelAgent:
    """为 FastAPI 依赖注入构建 Sentinel 核心编排服务。"""
    return build_sentinel_agent()


SentinelAgentDep = Annotated[SentinelAgent, Depends(get_sentinel_agent)]
