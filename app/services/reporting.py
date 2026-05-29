"""
报告渲染服务，负责根据 GitHub 活动数据渲染报告摘要。
定义报告渲染协议 `ReportRenderer`，用于隔离模板摘要、规则摘要或 LLM 摘要实现
"""
from typing import Protocol

from app.services.github_client import GitHubActivity


class ReportRenderer(Protocol):
    """报告渲染协议，用于隔离规则模板、LLM 摘要等不同实现。"""

    def render_digest(self, owner: str, repo: str, activities: list[GitHubActivity]) -> str:
        """把标准化活动列表渲染为可存储和通知的报告正文。"""
        raise NotImplementedError


class MarkdownReportRenderer:
    """使用轻量 Markdown 模板生成仓库动态摘要。"""

    def render_digest(self, owner: str, repo: str, activities: list[GitHubActivity]) -> str:
        """生成包含事件类型、标题、链接和发生时间的中文摘要。"""
        if not activities:
            return f"{owner}/{repo} 暂无新的仓库动态。"

        lines = [f"{owner}/{repo} 本次共获取 {len(activities)} 条新动态："]
        for index, activity in enumerate(activities, start=1):
            occurred_at = activity.occurred_at.isoformat()
            lines.append(
                f"{index}. [{activity.event_type}] {activity.title}\n"
                f"   - 链接：{activity.url}\n"
                f"   - 时间：{occurred_at}",
            )
        return "\n".join(lines)
