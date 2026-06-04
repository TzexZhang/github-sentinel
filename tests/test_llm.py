from datetime import datetime, timezone

import httpx

from app.services.github_client import GitHubActivity
from app.core.config import Settings
import pytest

from app.services.llm import (
    LLMError,
    REPORT_SYSTEM_PROMPT,
    OpenAICompatibleLLMClient,
    build_llm_client,
)
from app.services.reporting import build_repository_report_prompt


async def test_openai_compatible_llm_client_generates_markdown_from_chat_completion():
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "# acme/sentinel\n\n## Summary\n\n- Added report flow"
                        },
                    },
                ],
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = OpenAICompatibleLLMClient(
            api_key="test-key",
            model="glm-4-flash",
            endpoint="https://open.bigmodel.cn/api/paas/v4/chat/completions",
            http_client=http_client,
        )
        markdown = await client.generate_markdown("Summarize repository events.")

    assert markdown == "# acme/sentinel\n\n## Summary\n\n- Added report flow"
    assert requests[0].url == httpx.URL(
        "https://open.bigmodel.cn/api/paas/v4/chat/completions",
    )
    assert requests[0].headers["authorization"] == "Bearer test-key"
    assert requests[0].headers["content-type"] == "application/json"
    payload = requests[0].read()
    assert payload
    assert REPORT_SYSTEM_PROMPT.encode() in payload
    assert "新增功能".encode() in payload
    assert "主要改进".encode() in payload
    assert "修复问题".encode() in payload


async def test_openai_compatible_llm_client_wraps_request_timeout_as_llm_error():
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = OpenAICompatibleLLMClient(
            api_key="test-key",
            model="glm-4-flash",
            endpoint="https://open.bigmodel.cn/api/paas/v4/chat/completions",
            http_client=http_client,
        )

        with pytest.raises(LLMError, match="LLM 服务请求超时，可调大 LLM_TIMEOUT_SECONDS"):
            await client.generate_markdown("Summarize repository events.")


def test_build_llm_client_defaults_to_zhipu_free_model_when_api_key_is_present():
    client = build_llm_client(
        provider="zhipu",
        api_key="test-key",
        model=None,
        base_url=None,
        timeout=30.0,
    )

    assert isinstance(client, OpenAICompatibleLLMClient)
    assert client.model == "glm-4-flash"
    assert client.endpoint == "https://open.bigmodel.cn/api/paas/v4/chat/completions"


def test_build_llm_client_supports_gemini_free_series_provider():
    client = build_llm_client(
        provider="gemini",
        api_key="test-key",
        model=None,
        base_url=None,
        timeout=30.0,
    )

    assert isinstance(client, OpenAICompatibleLLMClient)
    assert client.model == "gemini-2.5-flash"
    assert client.endpoint == (
        "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    )


def test_settings_resolves_provider_specific_llm_api_key():
    zhipu_settings = Settings(llm_provider="zhipu", zhipu_api_key="zhipu-key")
    gemini_settings = Settings(llm_provider="gemini", gemini_api_key="gemini-key")

    assert zhipu_settings.resolved_llm_api_key == "zhipu-key"
    assert gemini_settings.resolved_llm_api_key == "gemini-key"


def test_build_repository_report_prompt_contains_push_and_issues_context():
    prompt = build_repository_report_prompt(
        owner="acme",
        repo="sentinel",
        activities=[
            GitHubActivity(
                external_id="push-1",
                event_type="PushEvent",
                title="Add LLM report",
                url="https://github.com/acme/sentinel/commit/1",
                occurred_at=datetime(2026, 5, 30, tzinfo=timezone.utc),
            ),
            GitHubActivity(
                external_id="issue-1",
                event_type="IssuesEvent",
                title="Track issue updates",
                url="https://github.com/acme/sentinel/issues/1",
                occurred_at=datetime(2026, 5, 30, tzinfo=timezone.utc),
            ),
        ],
        occurred_since=datetime(2026, 5, 29, tzinfo=timezone.utc),
        occurred_before=datetime(2026, 5, 31, tzinfo=timezone.utc),
    )

    assert "只返回 Markdown" in prompt
    assert "acme/sentinel" in prompt
    assert "2026-05-29 08:00:00 至 2026-05-31 08:00:00" in prompt
    assert "时间：2026-05-30 08:00:00" in prompt
    assert "标题日期：请使用报告时间范围的开始日期和结束日期" in prompt
    assert "# 简报：acme/sentinel （2026-05-29 ~ 2026-05-31）" in prompt
    assert "## 1. 新增功能" in prompt
    assert "## 2. 主要改进" in prompt
    assert "## 3. 修复问题" in prompt
    assert "暂无明确记录" in prompt
    assert "PushEvent" in prompt
    assert "IssuesEvent" in prompt
