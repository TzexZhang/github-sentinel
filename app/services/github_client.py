"""
仓库抓取服务，负责从 GitHub 或 Gitee 获取仓库动态并转换为统一活动模型。
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

import httpx

from app.core.errors import ApiError
from app.services.tokens import decrypt_token


@dataclass(frozen=True)
class GitHubActivity:
    """统一描述代码托管平台仓库动态，屏蔽 GitHub 与 Gitee 的事件结构差异。"""

    external_id: str
    event_type: str
    title: str
    url: str
    occurred_at: datetime


class GitHubClient(Protocol):
    """仓库动态抓取协议，用于隔离真实 HTTP 实现和测试替身。"""

    async def fetch_repository_activity(
        self,
        platform: str,
        owner: str,
        repo: str,
        access_token_encrypted: str,
        since: datetime | None,
    ) -> list[GitHubActivity]:
        """获取指定仓库的动态列表，并返回标准化后的活动数据。"""
        raise NotImplementedError


class HttpRepositoryClient:
    """基于 HTTP API 的仓库动态抓取客户端，支持 GitHub 与 Gitee。"""

    def __init__(
        self,
        http_client: httpx.AsyncClient | None = None,
        timeout: float = 10.0,
    ) -> None:
        """初始化 HTTP 客户端；测试可注入 MockTransport，生产默认创建短生命周期客户端。"""
        self._http_client = http_client
        self._timeout = timeout

    async def fetch_repository_activity(
        self,
        platform: str,
        owner: str,
        repo: str,
        access_token_encrypted: str,
        since: datetime | None,
    ) -> list[GitHubActivity]:
        """从远程平台抓取仓库事件，并按 since 过滤旧事件。"""
        token = _decrypt_optional_token(access_token_encrypted)
        if self._http_client is not None:
            activities = await self._fetch_with_client(self._http_client, platform, owner, repo, token)
        else:
            async with httpx.AsyncClient(timeout=self._timeout) as http_client:
                activities = await self._fetch_with_client(http_client, platform, owner, repo, token)

        if since is None:
            return activities
        return [activity for activity in activities if activity.occurred_at > since]

    async def _fetch_with_client(
        self,
        http_client: httpx.AsyncClient,
        platform: str,
        owner: str,
        repo: str,
        token: str | None,
    ) -> list[GitHubActivity]:
        """使用给定 HTTP 客户端完成一次远程请求并解析响应。"""
        if platform == "github":
            return await self._fetch_github_events(http_client, owner, repo, token)
        if platform == "gitee":
            return await self._fetch_gitee_events(http_client, owner, repo, token)
        raise ApiError(
            status_code=422,
            code="unsupported_platform",
            message="暂不支持该代码托管平台。",
        )

    async def _fetch_github_events(
        self,
        http_client: httpx.AsyncClient,
        owner: str,
        repo: str,
        token: str | None,
    ) -> list[GitHubActivity]:
        """调用 GitHub 仓库 Events API 并转换为统一活动列表。"""
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "github-sentinel",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"

        response = await _request_remote(
            http_client,
            "GET",
            f"https://api.github.com/repos/{owner}/{repo}/events",
            headers=headers,
        )
        payload = _ensure_list_payload(response)
        activities: list[GitHubActivity] = []
        for item in payload:
            activities.extend(_parse_github_event(item, owner, repo))
        return activities

    async def _fetch_gitee_events(
        self,
        http_client: httpx.AsyncClient,
        owner: str,
        repo: str,
        token: str | None,
    ) -> list[GitHubActivity]:
        """调用 Gitee 仓库 Events API 并转换为统一活动列表。"""
        params = {"access_token": token} if token else None
        response = await _request_remote(
            http_client,
            "GET",
            f"https://gitee.com/api/v5/repos/{owner}/{repo}/events",
            params=params,
            headers={"User-Agent": "github-sentinel"},
        )
        payload = _ensure_list_payload(response)
        activities: list[GitHubActivity] = []
        for item in payload:
            activities.extend(_parse_gitee_event(item, owner, repo))
        return activities


def _decrypt_optional_token(access_token_encrypted: str) -> str | None:
    """解密可选访问令牌；空字符串表示公开仓库匿名访问。"""
    if not access_token_encrypted:
        return None
    try:
        return decrypt_token(access_token_encrypted)
    except Exception as exc:
        raise ApiError(
            status_code=500,
            code="token_decrypt_failed",
            message="访问令牌解密失败，请重新配置订阅令牌。",
        ) from exc


async def _request_remote(
    http_client: httpx.AsyncClient,
    method: str,
    url: str,
    **kwargs: Any,
) -> httpx.Response:
    """发送远程请求，并把网络错误和非成功状态转换为中文业务错误。"""
    try:
        response = await http_client.request(method, url, **kwargs)
    except httpx.HTTPError as exc:
        raise ApiError(
            status_code=502,
            code="repository_fetch_failed",
            message="仓库动态获取失败，请稍后重试。",
        ) from exc

    if response.status_code >= 400:
        raise ApiError(
            status_code=502,
            code="repository_fetch_failed",
            message="仓库动态获取失败，请检查仓库地址或访问令牌。",
        )
    return response


def _ensure_list_payload(response: httpx.Response) -> list[dict[str, Any]]:
    """校验远程响应必须是事件对象数组，避免异常结构进入业务层。"""
    try:
        payload = response.json()
    except ValueError as exc:
        raise ApiError(
            status_code=502,
            code="repository_response_invalid",
            message="仓库平台返回了无法解析的数据。",
        ) from exc

    if not isinstance(payload, list):
        raise ApiError(
            status_code=502,
            code="repository_response_invalid",
            message="仓库平台返回的数据格式不正确。",
        )
    return [item for item in payload if isinstance(item, dict)]


def _parse_github_event(item: dict[str, Any], owner: str, repo: str) -> list[GitHubActivity]:
    """把单条 GitHub 事件转换为一个或多个统一活动模型。"""
    event_id = str(item.get("id") or f"{item.get('type', 'event')}:{item.get('created_at', '')}")
    event_type = str(item.get("type") or "RepositoryEvent")
    payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
    occurred_at = _parse_datetime(str(item.get("created_at") or ""))
    if event_type == "PushEvent":
        commit_activities = _parse_github_push_commits(payload, owner, repo, event_id, occurred_at)
        if commit_activities:
            return commit_activities

    title, url = _github_event_title_and_url(payload, owner, repo, event_type)
    return [
        GitHubActivity(
            external_id=f"github:{event_id}",
            event_type=event_type,
            title=title,
            url=url,
            occurred_at=occurred_at,
        ),
    ]


def _parse_github_push_commits(
    payload: dict[str, Any],
    owner: str,
    repo: str,
    event_id: str,
    occurred_at: datetime,
) -> list[GitHubActivity]:
    """把 GitHub PushEvent 中的每条 commit 拆成独立活动记录。"""
    commits = payload.get("commits") if isinstance(payload.get("commits"), list) else []
    activities: list[GitHubActivity] = []
    for index, commit in enumerate(commits, start=1):
        if not isinstance(commit, dict):
            continue
        message = str(commit.get("message") or "代码提交")
        sha = str(commit.get("sha") or index)
        commit_url = f"https://github.com/{owner}/{repo}/commit/{sha}" if sha else f"https://github.com/{owner}/{repo}"
        activities.append(
            GitHubActivity(
                external_id=f"github:{event_id}:commit:{sha}",
                event_type="PushEvent",
                title=message,
                url=commit_url,
                occurred_at=occurred_at,
            ),
        )
    return activities


def _github_event_title_and_url(
    payload: dict[str, Any],
    owner: str,
    repo: str,
    event_type: str,
) -> tuple[str, str]:
    """根据 GitHub 事件载荷提取报告标题和详情链接。"""
    repo_url = f"https://github.com/{owner}/{repo}"
    issue = payload.get("issue") if isinstance(payload.get("issue"), dict) else None
    pull_request = (
        payload.get("pull_request") if isinstance(payload.get("pull_request"), dict) else None
    )
    release = payload.get("release") if isinstance(payload.get("release"), dict) else None
    commits = payload.get("commits") if isinstance(payload.get("commits"), list) else []

    if issue:
        return str(issue.get("title") or "Issue 更新"), str(issue.get("html_url") or repo_url)
    if pull_request:
        return str(pull_request.get("title") or "Pull Request 更新"), str(
            pull_request.get("html_url") or repo_url,
        )
    if release:
        title = release.get("name") or release.get("tag_name") or "Release 更新"
        return str(title), str(release.get("html_url") or repo_url)
    if commits and isinstance(commits[0], dict):
        return str(commits[0].get("message") or "代码提交"), repo_url
    return _humanize_event_type(event_type), repo_url


def _parse_gitee_event(item: dict[str, Any], owner: str, repo: str) -> list[GitHubActivity]:
    """把单条 Gitee 事件转换为一个或多个统一活动模型。"""
    event_id = str(item.get("id") or f"{item.get('type', 'event')}:{item.get('created_at', '')}")
    event_type = str(item.get("type") or "RepositoryEvent")
    occurred_at = _parse_datetime(str(item.get("created_at") or ""))
    if event_type == "PushEvent":
        commit_activities = _parse_gitee_push_commits(item, owner, repo, event_id, occurred_at)
        if commit_activities:
            return commit_activities

    target = item.get("target") if isinstance(item.get("target"), dict) else {}
    title = str(target.get("title") or item.get("human_name") or _humanize_event_type(event_type))
    url = str(target.get("html_url") or f"https://gitee.com/{owner}/{repo}")
    return [
        GitHubActivity(
            external_id=f"gitee:{event_id}",
            event_type=event_type,
            title=title,
            url=url,
            occurred_at=occurred_at,
        ),
    ]


def _parse_gitee_push_commits(
    item: dict[str, Any],
    owner: str,
    repo: str,
    event_id: str,
    occurred_at: datetime,
) -> list[GitHubActivity]:
    """把 Gitee PushEvent 中的每条 commit 拆成独立活动记录。"""
    payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
    commits = payload.get("commits") or item.get("commits")
    if not isinstance(commits, list):
        return []

    activities: list[GitHubActivity] = []
    for index, commit in enumerate(commits, start=1):
        if not isinstance(commit, dict):
            continue
        message = str(commit.get("message") or "代码提交")
        sha = str(commit.get("sha") or commit.get("id") or index)
        commit_url = str(commit.get("url") or f"https://gitee.com/{owner}/{repo}/commit/{sha}")
        activities.append(
            GitHubActivity(
                external_id=f"gitee:{event_id}:commit:{sha}",
                event_type="PushEvent",
                title=message,
                url=commit_url,
                occurred_at=occurred_at,
            ),
        )
    return activities


def _parse_datetime(value: str) -> datetime:
    """解析远程平台时间字符串，缺失时返回当前本地时区时间兜底。"""
    if not value:
        return datetime.now().astimezone()
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def _humanize_event_type(event_type: str) -> str:
    """把事件类型转换为适合报告展示的短标题。"""
    labels = {
        "CreateEvent": "创建了资源",
        "DeleteEvent": "删除了资源",
        "ForkEvent": "Fork 了仓库",
        "IssuesEvent": "Issue 更新",
        "IssueEvent": "Issue 更新",
        "PullRequestEvent": "Pull Request 更新",
        "PushEvent": "代码提交",
        "ReleaseEvent": "Release 更新",
        "WatchEvent": "Star 更新",
    }
    return labels.get(event_type, event_type or "仓库动态")
