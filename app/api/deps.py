"""FastAPI 依赖注入别名。"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_session
from app.services.github_client import HttpRepositoryClient
from app.services.llm import build_llm_client
from app.services.notifications import NullNotificationSender
from app.services.reporting import MarkdownReportRenderer
from app.services.sentinel import SentinelAgent

DbSession = Annotated[AsyncSession, Depends(get_session)]


async def get_sentinel_agent() -> SentinelAgent:
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


SentinelAgentDep = Annotated[SentinelAgent, Depends(get_sentinel_agent)]
