from datetime import datetime, timezone

import httpx
import pytest

from app.core.config import Settings
from app.services.github_client import GitHubActivity
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

        with pytest.raises(LLMError, match="LLM"):
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
    assert "# 简报：acme/sentinel（2026-05-29 ~ 2026-05-31）" in prompt
    assert "## 1. 新增功能" in prompt
    assert "## 2. 主要改进" in prompt
    assert "## 3. 修复问题" in prompt
    assert "暂无明确记录" in prompt
    assert "PushEvent" in prompt
    assert "IssuesEvent" in prompt


def test_build_repository_report_prompt_requires_merging_duplicate_descriptions():
    prompt = build_repository_report_prompt(
        owner="acme",
        repo="sentinel",
        activities=[
            GitHubActivity(
                external_id="push-1",
                event_type="PushEvent",
                title="试题管理功能： 新增修改增加批量设置功能；",
                url="https://github.com/acme/sentinel/commit/1",
                occurred_at=datetime(2026, 5, 30, tzinfo=timezone.utc),
            ),
            GitHubActivity(
                external_id="push-2",
                event_type="PushEvent",
                title="试题管理功能： 添加试题调整参考答案；",
                url="https://github.com/acme/sentinel/commit/2",
                occurred_at=datetime(2026, 5, 30, tzinfo=timezone.utc),
            ),
        ],
        occurred_since=datetime(2026, 5, 29, tzinfo=timezone.utc),
        occurred_before=datetime(2026, 5, 31, tzinfo=timezone.utc),
    )

    assert "从用户可感知的功能角度描述" in prompt
    assert "所有描述都以业务功能及结果为导向" in prompt
    assert "完整性优先于合并" in prompt
    assert "先提取事件列表中的全部功能事实" in prompt
    assert "合并不是摘要删减" in prompt
    assert "每个有业务意义的原始事件至少要能在输出中找到对应功能点" in prompt
    assert "分类优先于主题合并" in prompt
    assert "不要把改进和修复都塞进新增功能" in prompt
    assert "优化、调整、改为、刷新、性能、体验、规则变化归入“主要改进”" in prompt
    assert "修复、兜底、报错、异常、兼容问题归入“修复问题”" in prompt
    assert "减少代码实现细节" in prompt
    assert "过滤没有实际功能含义的维护记录" in prompt
    assert "英文路径、组件名、页面文件名、技术字段和内部状态名不要直接出现在报告中" in prompt
    assert "试题管理功能" in prompt
    assert "多个模块、页面或业务流程执行的是相同动作" in prompt
    assert "题库训练具体的训练页面”应改为“题库训练的训练页面" in prompt
    assert "如果一个主题是另一个主题的子页面或子流程，应合并到父级主题下" in prompt
    assert "表述为“训练页面：xxx”" in prompt
    assert "同一主题下有多个具体变化时" in prompt
    assert "不能把多个小点压成同一行" in prompt
    assert "普通 Markdown 子列表分点列出" in prompt
    assert "禁止输出“- **主题：** 变化1 变化2”这种行内格式" in prompt
    assert "批量设置" in prompt
    assert "参考答案" in prompt
    assert "- **模拟考试问答题：**\n    - 新增答案抽取与匹配能力" in prompt
    assert "- 按后端规则处理答案匹配条件，支持逗号、或关系和包含匹配" in prompt
    assert "- **题库训练、题库管理、试卷管理：**\n    - 路由激活时，页面接口重新刷新" in prompt
    assert "- **题库训练：**\n    - 菜单激活时，涉及页面接口重新刷新" in prompt
    assert "- 训练页面：直接通过标签页激活时，补充兜底处理，并将路由跳转参数调整为查询参数" in prompt
    assert "- **主题：**\n  - 说明优化、调整、规则变化、性能或体验改进" in prompt
