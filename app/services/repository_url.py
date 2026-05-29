from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class ParsedRepositoryUrl:
    """仓库地址解析结果，包含平台、路径和标准化 URL。"""

    platform: str
    owner: str
    repo: str
    normalized_url: str


def parse_repository_url(repository_url: str) -> ParsedRepositoryUrl:
    """解析 HTTP(S) 或 SSH 形式的 GitHub/Gitee 仓库地址。"""
    url = repository_url.strip()
    if url.startswith("git@"):
        return _parse_ssh_url(url)
    return _parse_http_url(url)


def _parse_http_url(repository_url: str) -> ParsedRepositoryUrl:
    """解析 HTTP(S) 仓库地址并提取平台、owner 和 repo。"""
    parsed = urlparse(repository_url)
    platform = _platform_from_host(parsed.hostname)
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if platform is None or len(parts) < 2:
        raise ValueError("Repository URL must be a GitHub or Gitee repository URL.")

    owner = parts[0]
    repo = _strip_git_suffix(parts[1])
    return ParsedRepositoryUrl(
        platform=platform,
        owner=owner,
        repo=repo,
        normalized_url=f"https://{parsed.hostname}/{owner}/{repo}",
    )


def _parse_ssh_url(repository_url: str) -> ParsedRepositoryUrl:
    """解析 git@host:owner/repo.git 形式的 SSH 仓库地址。"""
    try:
        host_part, path_part = repository_url.split(":", 1)
        host = host_part.split("@", 1)[1]
    except ValueError as exc:
        raise ValueError("Repository URL must be a GitHub or Gitee repository URL.") from exc

    platform = _platform_from_host(host)
    parts = [part for part in path_part.strip("/").split("/") if part]
    if platform is None or len(parts) < 2:
        raise ValueError("Repository URL must be a GitHub or Gitee repository URL.")

    owner = parts[0]
    repo = _strip_git_suffix(parts[1])
    return ParsedRepositoryUrl(
        platform=platform,
        owner=owner,
        repo=repo,
        normalized_url=f"https://{host}/{owner}/{repo}",
    )


def _platform_from_host(host: str | None) -> str | None:
    """根据域名识别当前支持的代码托管平台。"""
    normalized = (host or "").lower()
    if normalized == "github.com":
        return "github"
    if normalized == "gitee.com":
        return "gitee"
    return None


def _strip_git_suffix(repo: str) -> str:
    """去除仓库名中的 .git 后缀。"""
    if repo.endswith(".git"):
        return repo[:-4]
    return repo
