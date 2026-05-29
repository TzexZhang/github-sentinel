"""
定义通知服务，负责发送通知邮件、Webhook、Slack 等。
定义通知发送协议 `NotificationSender`，用于隔离邮件、Webhook、Slack、企业微信等具体通知实现。
"""
from typing import Protocol


class NotificationSender(Protocol):
    """通知发送协议，隐藏邮件、Webhook、Slack 等具体通道差异。"""

    async def send(self, channel: str, subject: str, body: str) -> None:
        """向指定通知通道发送报告主题和正文。"""
        raise NotImplementedError


class NullNotificationSender:
    """空通知发送器，用于未接入真实通知系统时保持编排流程可运行。"""

    async def send(self, channel: str, subject: str, body: str) -> None:
        """忽略通知发送请求，避免在本地开发阶段触发外部副作用。"""
        return None
