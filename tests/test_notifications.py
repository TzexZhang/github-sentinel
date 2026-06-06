import json

import httpx
import pytest

from app.db.models import NotificationChannel
from app.services.notifications import (
    NotificationDeliveryError,
    NotificationRouter,
    SmtpNotificationSender,
    WeComNotificationSender,
    WebhookNotificationSender,
    build_email_message,
)


async def test_notification_router_dispatches_by_channel_type():
    class RecordingSender:
        def __init__(self) -> None:
            self.calls: list[tuple[NotificationChannel, str, str]] = []

        async def send(self, channel: NotificationChannel, subject: str, body: str) -> None:
            self.calls.append((channel, subject, body))

    smtp = RecordingSender()
    router = NotificationRouter(
        smtp_sender=smtp,
        wecom_sender=RecordingSender(),
        webhook_sender=RecordingSender(),
    )
    channel = NotificationChannel(name="team-mail", channel_type="smtp", target="team@example.com")

    await router.send(channel, "Daily report", "# body")

    assert smtp.calls == [(channel, "Daily report", "# body")]


async def test_notification_router_rejects_unknown_channel_type():
    router = NotificationRouter(
        smtp_sender=SmtpNotificationSender(),
        wecom_sender=WeComNotificationSender(),
        webhook_sender=WebhookNotificationSender(),
    )
    channel = NotificationChannel(name="unknown", channel_type="sms", target="team")

    with pytest.raises(NotificationDeliveryError, match="不支持的通知通道类型"):
        await router.send(channel, "Daily report", "# body")


async def test_smtp_sender_requires_configuration():
    sender = SmtpNotificationSender()
    channel = NotificationChannel(name="team-mail", channel_type="smtp", target="team@example.com")

    with pytest.raises(NotificationDeliveryError, match="SMTP 通知配置不完整"):
        await sender.send(channel, "Daily report", "# body")


def test_build_email_message_uses_rendered_html_body():
    channel = NotificationChannel(name="team-mail", channel_type="smtp", target="team@example.com")

    message = build_email_message(
        channel=channel,
        from_email="sender@example.com",
        subject="Daily report",
        body_markdown="# 标题\n\n## 进展\n\n- **完成** [任务](https://example.com)\n- 修复问题",
    )

    content = message.get_content()

    assert message.get_content_type() == "text/html"
    assert "# 标题" not in content
    assert "<h1>标题</h1>" in content
    assert "<h2>进展</h2>" in content
    assert "<ul>" in content
    assert "<strong>完成</strong>" in content
    assert '<a href="https://example.com">任务</a>' in content


async def test_wecom_sender_requires_application_configuration():
    sender = WeComNotificationSender()
    channel = NotificationChannel(name="repo-alerts", channel_type="wecom", target="zhangtengying")

    with pytest.raises(NotificationDeliveryError, match="企业微信通知配置不完整"):
        await sender.send(channel, "Daily report", "# body")


async def test_wecom_sender_sends_full_text_split_into_multiple_messages():
    requests: list[tuple[str, dict[str, object]]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/gettoken"):
            requests.append((str(request.url), {}))
            return httpx.Response(200, json={"errcode": 0, "access_token": "token-1"})
        requests.append((str(request.url), json.loads(request.content)))
        return httpx.Response(200, json={"errcode": 0})

    sender = WeComNotificationSender(
        corp_id="corp-1",
        agent_id="1000002",
        secret="secret-1",
        default_to_user="fallback-user",
        max_content_chars=40,
        http_client_factory=lambda timeout: httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            timeout=timeout,
        ),
    )
    channel = NotificationChannel(name="repo-alerts", channel_type="wecom", target="zhangtengying")

    long_body = "# 标题\n\n- 第一项完整内容\n- 第二项完整内容\n- 第三项完整内容\n- 第四项完整内容"

    await sender.send(channel, "Daily report", long_body)

    assert requests[0][0] == (
        "https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid=corp-1&corpsecret=secret-1"
    )
    sent_payloads = [payload for _, payload in requests[1:]]
    assert len(sent_payloads) > 1
    assert all(payload["touser"] == "zhangtengying" for payload in sent_payloads)
    assert all(len(payload["text"]["content"]) <= 40 for payload in sent_payloads)
    sent_text = "\n".join(str(payload["text"]["content"]) for payload in sent_payloads)
    assert "Daily report" in sent_text
    assert "标题" in sent_text
    assert "第一项完整内容" in sent_text
    assert "第二项完整内容" in sent_text
    assert "第三项完整内容" in sent_text
    assert "第四项完整内容" in sent_text
    assert "完整报告请登录 Git Sentinel 报告中心查看" not in sent_text


async def test_wecom_sender_uses_default_to_user_when_channel_target_is_blank():
    requests: list[dict[str, object]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/gettoken"):
            return httpx.Response(200, json={"errcode": 0, "access_token": "token-1"})
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={"errcode": 0})

    sender = WeComNotificationSender(
        corp_id="corp-1",
        agent_id="1000002",
        secret="secret-1",
        default_to_user="fallback-user",
        http_client_factory=lambda timeout: httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            timeout=timeout,
        ),
    )
    channel = NotificationChannel(name="repo-alerts", channel_type="wecom", target="")

    await sender.send(channel, "Daily report", "# body")

    assert requests[0]["touser"] == "fallback-user"


async def test_webhook_sender_requires_webhook_url():
    sender = WebhookNotificationSender()
    channel = NotificationChannel(name="release-bot", channel_type="webhook", target="release-bot")

    with pytest.raises(NotificationDeliveryError, match="Webhook 通知配置不完整"):
        await sender.send(channel, "Daily report", "# body")


async def test_webhook_sender_posts_rendered_text_and_html_instead_of_markdown():
    requests: list[dict[str, object]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(200)

    sender = WebhookNotificationSender(
        webhook_url="https://example.com/webhook",
        http_client_factory=lambda timeout: httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            timeout=timeout,
        ),
    )
    channel = NotificationChannel(name="release-bot", channel_type="webhook", target="release-bot")

    await sender.send(channel, "Daily report", "# 标题\n\n- **完成** [任务](https://example.com)")

    assert len(requests) == 1
    payload = requests[0]
    assert payload["channel"] == "release-bot"
    assert payload["subject"] == "Daily report"
    assert payload["body_text"] == "标题\n\n- 完成 任务 (https://example.com)"
    assert "<h1>标题</h1>" in str(payload["body_html"])
    assert "body_markdown" not in payload
