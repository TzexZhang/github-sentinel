from datetime import UTC, timedelta
from typing import Protocol

from app.services.github_client import GitHubActivity
from app.services.time_utils import format_report_datetime


class ReportRenderer(Protocol):
    """把标准化仓库动态渲染为可入库的 Markdown 简报。"""

    def render_digest(self, owner: str, repo: str, activities: list[GitHubActivity]) -> str:
        """根据仓库身份和动态列表生成 Markdown 简报正文。"""
        raise NotImplementedError


class MarkdownReportRenderer:
    """未配置或无法使用 LLM 客户端时的备用 Markdown 渲染器。"""

    def render_digest(self, owner: str, repo: str, activities: list[GitHubActivity]) -> str:
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
    """构建 LLM 生成 Markdown 报告时使用的提示词。"""
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
        "- 所有描述都以业务功能及结果为导向：说明用户能看到什么能力、流程有什么变化、问题带来什么结果；不要从代码实现角度描述。",
        "- 完整性优先于合并：先提取事件列表中的全部功能事实，再按主题合并表达；不要因为合并而遗漏新增、调整、支持、修复、优化、规则变化等具体点。",
        "- 合并不是摘要删减：合并后的每个子项都必须能对应到一个或多个原始事件；每个有业务意义的原始事件至少要能在输出中找到对应功能点。",
        "- 分类优先于主题合并：先判断每个事实属于“新增功能”“主要改进”还是“修复问题”，再在同一分类内合并相同主题；不要把改进和修复都塞进新增功能。",
        "- 分类规则：新增、支持、接入、增加能力归入“新增功能”；优化、调整、改为、刷新、性能、体验、规则变化归入“主要改进”；修复、兜底、报错、异常、兼容问题归入“修复问题”。",
        "- 每条要点从用户可感知的功能角度描述，优先说明模块、能力、使用体验、规则变化和修复效果。",
        "- 减少代码实现细节，不要把提交中的文件名、函数名、类名、变量名、重构手法作为主要内容；除非它们本身就是用户可见能力。",
        "- 过滤没有实际功能含义的维护记录，例如代码恢复、代码整理、格式调整、临时回滚、文件移动；无法转成用户可感知变化时不要写入报告。",
        "- 尽量使用中文业务描述；英文路径、组件名、页面文件名、技术字段和内部状态名不要直接出现在报告中，应转成中文功能表达或舍弃。",
        "- 如果某个分类没有可归纳的事件，保留分类标题并写“暂无明确记录”。",
        "- 合并重复或高度相似的内容；同一模块、同一功能域、同一页面或同一业务流程的相近提交要合并成一条要点，不要拆成多条。",
        "- 如果多个模块、页面或业务流程执行的是相同动作，应合并为“模块A、模块B、模块C：同一动作”，不要按模块拆成多条重复描述。",
        "- 主题名称要自然、简洁，去掉“具体的”等口语冗余；例如“题库训练具体的训练页面”应改为“题库训练的训练页面”。",
        "- 如果一个主题是另一个主题的子页面或子流程，应合并到父级主题下；小点中保留子页面名称，例如“题库训练的训练页面：xxx”应写在“题库训练”主题下，表述为“训练页面：xxx”。",
        "- 同一主题下有多个具体变化时，主题只出现一次，后面用普通 Markdown 子列表分点列出；每个小点必须单独换行，不能把多个小点压成同一行。",
        "- 多点条目必须使用以下 Markdown 换行格式：第一行只写“- **主题：**”，后续每个小点写成缩进两个空格的“- 具体变化”；禁止输出“- **主题：** 变化1 变化2”这种行内格式。",
        "- 示例：将“模拟考试问答题：新增抽取匹配逻辑为公共工具方法。模拟考试问答题：改为单输入框，正确答案展示。模拟考试问答题：按后端规则处理 optionContext，支持逗号 AND、|| OR、includes 匹配。”整理为：\n"
        "  - **模拟考试问答题：**\n"
        "    - 新增答案抽取与匹配能力\n"
        "    - 调整为单输入框，并展示正确答案\n"
        "    - 按后端规则处理答案匹配条件，支持逗号、或关系和包含匹配",
        "- 示例：将“题库训练：试题管理-菜单激活时保证涉及到的页面接口重新刷新。题库管理 试卷管理：在路由激活时，主动刷新页面的接口调用。”整理为：\n"
        "  - **题库训练、题库管理、试卷管理：**\n"
        "    - 路由激活时，页面接口重新刷新",
        "- 示例：将“题库训练：菜单激活时保证涉及到的页面接口重新刷新。题库训练具体的训练页面：直接通过 tabs 激活时，没有兜底报错问题，路由跳转 state 改为 query。”整理为：\n"
        "  - **题库训练：**\n"
        "    - 菜单激活时，涉及页面接口重新刷新\n"
        "    - 训练页面：直接通过标签页激活时，补充兜底处理，并将路由跳转参数调整为查询参数",
        f"仓库：{owner}/{repo}",
        (
            "报告时间范围："
            f"{format_report_datetime(occurred_since, naive_timezone=UTC)} 至 "
            f"{format_report_datetime(occurred_before, naive_timezone=UTC)}"
        ),
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
            f"# 简报：{owner}/{repo}（{report_start_date} ~ {report_end_date}）",
            "",
            f"下面是 {owner}/{repo} 项目在本时间范围内的最新进展情况，"
            "包括新增功能、主要改进和修复的问题。",
            "",
            "## 1. 新增功能",
            "",
            "- **主题：**",
            "  - 说明新增能力或新内容；没有则写“暂无明确记录”。",
            "",
            "## 2. 主要改进",
            "",
            "- **主题：**",
            "  - 说明优化、调整、规则变化、性能或体验改进；没有则写“暂无明确记录”。",
            "",
            "## 3. 修复问题",
            "",
            "- **主题：**",
            "  - 说明缺陷修复、兜底处理、兼容性修复或问题处理；没有则写“暂无明确记录”。",
            "",
        ],
    )
    return "\n".join(lines)
