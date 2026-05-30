"""
报告渲染服务，负责根据 GitHub 活动数据渲染报告摘要。
定义报告渲染协议 `ReportRenderer`，用于隔离模板摘要、规则摘要或 LLM 摘要实现
"""
from datetime import UTC, timedelta
from typing import Protocol

from app.services.github_client import GitHubActivity
from app.services.time_utils import format_report_datetime


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
            occurred_at = format_report_datetime(activity.occurred_at, naive_timezone=UTC)
            lines.append(
                f"{index}. [{activity.event_type}] {activity.title}\n"
                f"   - 链接：{activity.url}\n"
                f"   - 时间：{occurred_at}",
            )
        return "\n".join(lines)


def build_repository_report_prompt(
    owner: str,
    repo: str,
    activities: list[GitHubActivity],
    occurred_since,
    occurred_before,
) -> str:
    """构建 LLM 生成 Markdown 报告时使用的稳定提示词。"""
    report_start_date = format_report_datetime(occurred_since, naive_timezone=UTC).split(" ")[0]
    report_end_date = format_report_datetime(
        occurred_before - timedelta(seconds=1),
        naive_timezone=UTC,
    ).split(" ")[0]
    lines = [
        "请根据以下仓库事件生成一份中文项目进展简报。",
        "输出要求：",
        "- 只返回 Markdown 正文，不要输出代码块围栏。",
        "- 报告必须参考给定模板结构，不要新增无关章节。",
        "- 内容只能来自事件列表；不要编造版本号、负责人、影响范围或未出现的技术细节。",
        "- 每条要点使用简短中文说明，优先提炼标题中的模块、功能、修复点。",
        "- 如果某个分类没有可归纳的事件，保留分类标题并写“暂无明确记录”。",
        f"仓库：{owner}/{repo}",
        "报告时间范围："
        f"{format_report_datetime(occurred_since, naive_timezone=UTC)} 至 "
        f"{format_report_datetime(occurred_before, naive_timezone=UTC)}",
        "标题日期：请使用报告时间范围的开始日期和结束日期，格式为 YYYY-MM-DD ~ YYYY-MM-DD。",
        "",
        "事件列表：",
    ]
    if not activities:
        lines.append("无 PushEvent 或 IssuesEvent。")
    for index, activity in enumerate(activities, start=1):
        lines.extend(
            [
                f"{index}. 类型：{activity.event_type}",
                f"   时间：{format_report_datetime(activity.occurred_at, naive_timezone=UTC)}",
                f"   标题：{activity.title}",
                f"   链接：{activity.url}",
            ],
        )

    lines.extend(
        [
            "",
            "请严格使用以下 Markdown 模板：",
            f"# 简报：{owner}/{repo} （{report_start_date} ~ {report_end_date}）",
            "",
            f"下面是 {owner}/{repo} 项目在本时间范围内的最新进展情况，"
            "包括新增功能、主要改进和修复的问题。",
            "",
            "## 1. 新增功能",
            "",
            "- **主题：** 说明新增能力或新内容；没有则写“暂无明确记录”。",
            "",
            "## 2. 主要改进",
            "",
            "- **主题：** 说明优化、重构、依赖升级、文档更新或使用方式变化；"
            "没有则写“暂无明确记录”。",
            "",
            "## 3. 修复问题",
            "",
            "- **主题：** 说明缺陷修复、兼容性修复或问题处理；没有则写“暂无明确记录”。",
            "",
            "本次进展报告涵盖了项目的重要更新和优化措施，旨在提高系统稳定性和用户体验。",
        ],
    )
    return "\n".join(lines)
