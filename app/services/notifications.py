"""通知发送协议、路由器和真实通道适配器。"""

import asyncio
from collections.abc import Callable
import html
import re
import smtplib
from email.message import EmailMessage
from typing import Protocol

import httpx

from app.db.models import NotificationChannel


class NotificationDeliveryError(Exception):
    """通知投递失败，调用方应记录到通知任务状态中。"""


class NotificationSender(Protocol):
    """通知发送协议，隐藏 SMTP、企业微信、Webhook 等具体通道差异。"""

    async def send(self, channel: NotificationChannel, subject: str, body: str) -> None:
        """向指定通知通道发送报告主题和正文。"""
        raise NotImplementedError


class NotificationRouter:
    """根据通知通道类型选择具体发送适配器。"""

    def __init__(
        self,
        smtp_sender: NotificationSender,
        wecom_sender: NotificationSender,
        webhook_sender: NotificationSender,
    ) -> None:
        self._senders = {
            "smtp": smtp_sender,
            "wecom": wecom_sender,
            "dingtalk": wecom_sender,
            "webhook": webhook_sender,
        }

    async def send(self, channel: NotificationChannel, subject: str, body: str) -> None:
        sender = self._senders.get(channel.channel_type)
        if sender is None:
            raise NotificationDeliveryError(f"不支持的通知通道类型：{channel.channel_type}")
        await sender.send(channel, subject, body)


class SmtpNotificationSender:
    """通过 SMTP 发送邮件通知。"""

    def __init__(
        self,
        host: str | None = None,
        port: int = 587,
        username: str | None = None,
        password: str | None = None,
        from_email: str | None = None,
        use_tls: bool = True,
        use_ssl: bool = False,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._from_email = from_email
        self._use_tls = use_tls
        self._use_ssl = use_ssl

    async def send(self, channel: NotificationChannel, subject: str, body: str) -> None:
        if not self._host or not self._from_email:
            raise NotificationDeliveryError("SMTP 通知配置不完整。")

        message = build_email_message(channel, self._from_email, subject, body)
        await asyncio.to_thread(self._send_message, message)

    def _send_message(self, message: EmailMessage) -> None:
        try:
            smtp_cls = smtplib.SMTP_SSL if self._use_ssl else smtplib.SMTP
            with smtp_cls(self._host, self._port, timeout=15) as smtp:
                if self._use_tls and not self._use_ssl:
                    smtp.starttls()
                if self._username and self._password:
                    smtp.login(self._username, self._password)
                smtp.send_message(message)
        except OSError as exc:
            raise NotificationDeliveryError(f"SMTP 通知发送失败：{exc}") from exc


def build_email_message(
    channel: NotificationChannel,
    from_email: str,
    subject: str,
    body_markdown: str,
) -> EmailMessage:
    """构建 HTML 邮件消息，将 Markdown 报告转换为邮箱可渲染内容。"""
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = from_email
    message["To"] = channel.target
    message.set_content(_markdown_to_email_html(body_markdown), subtype="html")
    return message


def _markdown_to_email_html(markdown: str) -> str:
    """转换报告常用 Markdown 子集为邮件 HTML。"""
    blocks: list[str] = []
    in_list = False

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            blocks.append("</ul>")
            in_list = False

    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line:
            close_list()
            continue
        if line.startswith("### "):
            close_list()
            blocks.append(f"<h3>{_render_inline_markdown(line[4:])}</h3>")
            continue
        if line.startswith("## "):
            close_list()
            blocks.append(f"<h2>{_render_inline_markdown(line[3:])}</h2>")
            continue
        if line.startswith("# "):
            close_list()
            blocks.append(f"<h1>{_render_inline_markdown(line[2:])}</h1>")
            continue
        if line.startswith("- "):
            if not in_list:
                blocks.append("<ul>")
                in_list = True
            blocks.append(f"<li>{_render_inline_markdown(line[2:])}</li>")
            continue
        close_list()
        blocks.append(f"<p>{_render_inline_markdown(line)}</p>")

    close_list()
    return "\n".join(
        [
            "<!doctype html>",
            '<html><body style="font-family: -apple-system, BlinkMacSystemFont, '
            "Segoe UI, sans-serif; line-height: 1.6; color: #1f2933;\">",
            *blocks,
            "</body></html>",
        ],
    )


def _markdown_to_text(markdown: str) -> str:
    """转换报告常用 Markdown 子集为普通文本。"""
    lines: list[str] = []
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if line.startswith("### "):
            lines.append(_render_inline_markdown_as_text(line[4:]))
            continue
        if line.startswith("## "):
            lines.append(_render_inline_markdown_as_text(line[3:]))
            continue
        if line.startswith("# "):
            lines.append(_render_inline_markdown_as_text(line[2:]))
            continue
        if line.startswith("- "):
            lines.append(f"- {_render_inline_markdown_as_text(line[2:])}")
            continue
        lines.append(_render_inline_markdown_as_text(line))
    return "\n".join(lines).strip()


def _render_inline_markdown(value: str) -> str:
    escaped = html.escape(value)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(
        r"\[([^\]]+)\]\((https?://[^)]+)\)",
        r'<a href="\2">\1</a>',
        escaped,
    )
    return escaped


def _render_inline_markdown_as_text(value: str) -> str:
    value = re.sub(r"\*\*(.+?)\*\*", r"\1", value)
    value = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"\1 (\2)", value)
    return value


class WeComNotificationSender:
    """通过企业微信自建应用向成员账号发送文本通知。"""

    def __init__(
        self,
        corp_id: str | None = None,
        agent_id: int | str | None = None,
        secret: str | None = None,
        default_to_user: str | None = None,
        timeout_seconds: float = 10.0,
        http_client_factory: Callable[[float], httpx.AsyncClient] | None = None,
    ) -> None:
        self._corp_id = corp_id
        self._agent_id = str(agent_id).strip() if agent_id not in (None, "") else None
        self._secret = secret
        self._default_to_user = default_to_user
        self._timeout_seconds = timeout_seconds
        self._http_client_factory = http_client_factory

    async def send(self, channel: NotificationChannel, subject: str, body: str) -> None:
        to_user = channel.target.strip() if channel.target else ""
        to_user = to_user or (self._default_to_user or "").strip()
        if not self._corp_id or self._agent_id is None or not self._secret or not to_user:
            raise NotificationDeliveryError("企业微信通知配置不完整。")
        try:
            agent_id = int(self._agent_id)
        except ValueError as exc:
            raise NotificationDeliveryError("企业微信 AgentId 必须是数字。") from exc

        payload = {
            "touser": to_user,
            "msgtype": "text",
            "agentid": agent_id,
            "text": {
                "content": f"{subject}\n\n{_markdown_to_text(body)}",
            },
            "safe": 0,
        }
        access_token = await self._fetch_access_token()
        await _post_json_checked(
            f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={access_token}",
            payload,
            self._timeout_seconds,
            http_client_factory=self._http_client_factory,
            error_prefix="企业微信通知发送失败",
        )

    async def _fetch_access_token(self) -> str:
        response = await _get_json_checked(
            "https://qyapi.weixin.qq.com/cgi-bin/gettoken"
            f"?corpid={self._corp_id}&corpsecret={self._secret}",
            self._timeout_seconds,
            http_client_factory=self._http_client_factory,
            error_prefix="企业微信 access_token 获取失败",
        )
        access_token = response.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise NotificationDeliveryError("企业微信 access_token 获取失败：响应缺少 access_token。")
        return access_token


class WebhookNotificationSender:
    """通过通用 HTTP Webhook 发送通知。"""

    def __init__(
        self,
        webhook_url: str | None = None,
        token: str | None = None,
        timeout_seconds: float = 10.0,
        http_client_factory: Callable[[float], httpx.AsyncClient] | None = None,
    ) -> None:
        self._webhook_url = webhook_url
        self._token = token
        self._timeout_seconds = timeout_seconds
        self._http_client_factory = http_client_factory

    async def send(self, channel: NotificationChannel, subject: str, body: str) -> None:
        if not self._webhook_url:
            raise NotificationDeliveryError("Webhook 通知配置不完整。")

        headers = {}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        payload = {
            "channel": channel.name,
            "target": channel.target,
            "subject": subject,
            "body_text": _markdown_to_text(body),
            "body_html": _markdown_to_email_html(body),
        }
        await _post_json(
            self._webhook_url,
            payload,
            self._timeout_seconds,
            headers=headers,
            http_client_factory=self._http_client_factory,
        )


class NullNotificationSender:
    """空通知发送器，用于未接入真实通知系统时保持编排流程可运行。"""

    async def send(self, channel: NotificationChannel, subject: str, body: str) -> None:
        """忽略通知发送请求，避免在本地开发阶段触发外部副作用。"""
        return None


async def _post_json(
    url: str,
    payload: dict[str, object],
    timeout_seconds: float,
    headers: dict[str, str] | None = None,
    http_client_factory: Callable[[float], httpx.AsyncClient] | None = None,
) -> None:
    try:
        client_factory = http_client_factory or (lambda timeout: httpx.AsyncClient(timeout=timeout))
        async with client_factory(timeout_seconds) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise NotificationDeliveryError(f"HTTP 通知发送失败：{exc}") from exc


async def _get_json_checked(
    url: str,
    timeout_seconds: float,
    http_client_factory: Callable[[float], httpx.AsyncClient] | None = None,
    error_prefix: str = "HTTP 请求失败",
) -> dict[str, object]:
    try:
        client_factory = http_client_factory or (lambda timeout: httpx.AsyncClient(timeout=timeout))
        async with client_factory(timeout_seconds) as client:
            response = await client.get(url)
            response.raise_for_status()
            payload = response.json()
    except (ValueError, httpx.HTTPError) as exc:
        raise NotificationDeliveryError(f"{error_prefix}：{exc}") from exc
    _raise_for_wecom_error(payload, error_prefix)
    return payload


async def _post_json_checked(
    url: str,
    payload: dict[str, object],
    timeout_seconds: float,
    http_client_factory: Callable[[float], httpx.AsyncClient] | None = None,
    error_prefix: str = "HTTP 通知发送失败",
) -> dict[str, object]:
    try:
        client_factory = http_client_factory or (lambda timeout: httpx.AsyncClient(timeout=timeout))
        async with client_factory(timeout_seconds) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            response_payload = response.json()
    except (ValueError, httpx.HTTPError) as exc:
        raise NotificationDeliveryError(f"{error_prefix}：{exc}") from exc
    _raise_for_wecom_error(response_payload, error_prefix)
    return response_payload


def _raise_for_wecom_error(payload: dict[str, object], error_prefix: str) -> None:
    errcode = payload.get("errcode", 0)
    if errcode not in (0, "0"):
        errmsg = payload.get("errmsg", "")
        raise NotificationDeliveryError(f"{error_prefix}：errcode={errcode}, errmsg={errmsg}")
