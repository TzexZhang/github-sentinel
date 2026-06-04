"""LLM 客户端抽象与内置服务商配置。"""

from typing import Any, Protocol

import httpx

REPORT_SYSTEM_PROMPT = (
    "你是 GitHub Sentinel 的项目进展简报助手，负责把仓库事件整理成清晰、克制、"
    "可直接保存的中文 Markdown 报告。输出必须只包含 Markdown 正文，不要输出代码块围栏、"
    "不要解释你的思考过程、不要编造事件列表中没有的信息。报告语气要像项目管理简报："
    "先给结论，再按新增功能、主要改进、修复问题分类总结；无法归类或没有证据的栏目写"
    "“暂无明确记录”。"
)


class LLMClient(Protocol):
    """通用 Markdown 生成客户端。"""

    async def generate_markdown(self, prompt: str) -> str:
        """根据文本提示词生成 Markdown 内容。"""
        raise NotImplementedError


class LLMError(Exception):
    """LLM 服务无法生成可用响应时抛出的异常。"""


class OpenAICompatibleLLMClient:
    """面向 OpenAI 兼容 Chat Completions 接口的 LLM 客户端。"""

    def __init__(
        self,
        api_key: str,
        model: str,
        endpoint: str,
        http_client: httpx.AsyncClient | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.endpoint = endpoint
        self._http_client = http_client
        self._timeout = timeout

    async def generate_markdown(self, prompt: str) -> str:
        """调用已配置的对话补全接口，并返回 Markdown 文本。"""
        if self._http_client is not None:
            return await self._generate_with_client(self._http_client, prompt)

        async with httpx.AsyncClient(timeout=self._timeout) as http_client:
            return await self._generate_with_client(http_client, prompt)

    async def _generate_with_client(self, http_client: httpx.AsyncClient, prompt: str) -> str:
        try:
            response = await http_client.post(
                self.endpoint,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": REPORT_SYSTEM_PROMPT,
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.2,
                },
            )
        except httpx.TimeoutException as exc:
            raise LLMError("LLM 服务请求超时，可调大 LLM_TIMEOUT_SECONDS。") from exc
        except httpx.RequestError as exc:
            raise LLMError("LLM 服务请求失败。") from exc

        if response.status_code >= 400:
            raise LLMError("LLM 服务返回了错误响应。")

        content = _extract_chat_completion_content(response)
        if not content:
            raise LLMError("LLM 服务返回了空响应。")
        return content


def build_llm_client(
    provider: str | None,
    api_key: str | None,
    model: str | None,
    base_url: str | None,
    timeout: float,
) -> LLMClient | None:
    """构建已配置的 LLM 客户端；未提供 API Key 时返回 None。"""
    if not api_key:
        return None

    normalized_provider = (provider or "zhipu").strip().lower()
    if normalized_provider in {"none", "off", "disabled"}:
        return None

    if normalized_provider == "zhipu":
        return OpenAICompatibleLLMClient(
            api_key=api_key,
            model=model or "glm-4-flash",
            endpoint=_chat_completions_endpoint(
                base_url or "https://open.bigmodel.cn/api/paas/v4",
            ),
            timeout=timeout,
        )

    if normalized_provider == "gemini":
        return OpenAICompatibleLLMClient(
            api_key=api_key,
            model=model or "gemini-2.5-flash",
            endpoint=_chat_completions_endpoint(
                base_url or "https://generativelanguage.googleapis.com/v1beta/openai",
            ),
            timeout=timeout,
        )

    return OpenAICompatibleLLMClient(
        api_key=api_key,
        model=model or normalized_provider,
        endpoint=_chat_completions_endpoint(base_url or ""),
        timeout=timeout,
    )


def _chat_completions_endpoint(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


def _extract_chat_completion_content(response: httpx.Response) -> str:
    try:
        payload: dict[str, Any] = response.json()
    except ValueError as exc:
        raise LLMError("LLM 服务返回了无法解析的 JSON。") from exc

    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        return ""
    message = first_choice.get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    return content.strip() if isinstance(content, str) else ""
