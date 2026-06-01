"""Gradio 可视化界面。"""

from datetime import date, datetime, timedelta

import gradio as gr

from app.api.deps import build_sentinel_agent
from app.core.errors import ApiError
from app.db.models import Report, Subscription
from app.db.session import AsyncSessionLocal
from app.repositories.reports import list_reports
from app.repositories.subscriptions import create_subscription, delete_subscription, list_subscriptions
from app.schemas.subscriptions import SubscriptionCreate
from app.services.time_utils import format_report_datetime
from app.services.time_utils import report_now

REPORT_WINDOW_CHOICES = [
    ("一天内", "1d"),
    ("三天内", "3d"),
    ("五天内", "5d"),
    ("一周内", "7d"),
    ("一月内", "30d"),
    ("自定义时间范围", "custom"),
]

REPORT_PREVIEW_HEAD = """
<script>document.documentElement.lang = "zh-CN";</script>
<style>
:root {
    --report-center-offset: 170px;
}
html,
body,
gradio-app,
.gradio-container {
    height: 100%;
    max-height: 100vh;
    overflow: hidden !important;
}
.report-center-shell {
    height: calc(100vh - var(--report-center-offset));
    min-height: 0;
    overflow: hidden !important;
}
.report-controls {
    align-content: stretch !important;
    align-items: stretch !important;
    flex-wrap: nowrap !important;
    height: calc(100vh - var(--report-center-offset));
    min-height: 0;
    overflow-y: auto !important;
    overflow-x: visible;
    padding: 2px 10px 2px 2px;
}
.report-controls > .gap {
    gap: 12px;
}
.report-controls > * {
    flex-shrink: 0 !important;
    max-width: 100% !important;
}
.report-action-section,
.report-generate-section {
    overflow: visible !important;
    border: 1px solid #dde5df !important;
    border-radius: 8px !important;
    background: #fbfcfa !important;
    box-shadow: none !important;
    padding: 12px !important;
}
.report-action-section .form,
.report-generate-section .form {
    overflow: visible !important;
}
.report-action-section > .styler,
.report-action-section .styler,
.report-generate-section > .styler,
.report-generate-section .styler {
    background: #fbfcfa !important;
    background-color: #fbfcfa !important;
    background-image: none !important;
    display: flex !important;
    flex-direction: column !important;
    gap: 12px !important;
    min-width: 0 !important;
    overflow: visible !important;
    width: 100% !important;
}
.report-preview-column {
    height: calc(100vh - var(--report-center-offset));
    min-height: 0;
    overflow: hidden !important;
    padding-right: 8px;
}
.report-preview-column > .gap {
    height: 100%;
    min-height: 0;
    display: flex;
    flex-direction: column;
}
.report-select-row {
    display: flex !important;
    gap: 8px;
    align-items: flex-end !important;
}
.report-select-row > :first-child {
    flex: 1 1 auto !important;
    min-width: 0 !important;
}
.report-select-row > *:has(.report-query-button) {
    align-self: flex-end !important;
    background: #2f6b4f !important;
    border: 1px solid #2f6b4f !important;
    border-radius: 6px !important;
    box-shadow: none !important;
    flex: 0 0 92px !important;
    height: 40px !important;
    margin: 0 !important;
    max-width: 92px !important;
    min-width: 92px !important;
    overflow: hidden !important;
    padding: 0 !important;
    transform: translateY(-10px);
}
.report-select-row .report-query-button {
    align-self: flex-end !important;
    background: #2f6b4f !important;
    border: 1px solid #2f6b4f !important;
    border-radius: 6px !important;
    box-shadow: none !important;
    flex: 0 0 92px !important;
    height: 40px !important;
    line-height: 1 !important;
    margin: 0 !important;
    max-width: 92px !important;
    min-width: 92px !important;
    overflow: hidden !important;
    padding: 0 !important;
    color: #ffffff !important;
    transform: translateY(-10px);
}
.report-select-row > *:has(.report-query-button):hover,
.report-select-row .report-query-button:hover {
    background: #2f6b4f !important;
    border: 1px solid #2f6b4f !important;
    box-shadow: none !important;
    color: #ffffff !important;
    transform: translateY(-10px) !important;
}
.report-select-row .report-query-button button,
.report-select-row button {
    border-color: #2f6b4f !important;
    background: #2f6b4f !important;
    color: #ffffff !important;
    height: 40px !important;
    line-height: 1;
    margin: 0 !important;
    width: 100% !important;
}
.report-select-row .report-query-button button:hover {
    background: #2f6b4f !important;
    border-color: #2f6b4f !important;
    box-shadow: none !important;
    color: #ffffff !important;
}
.report-date-inline {
    display: flex !important;
    gap: 10px;
    align-items: stretch !important;
    width: 100%;
    overflow: visible !important;
}
.report-date-inline > *,
.report-date-inline .report-date-field {
    flex: 1 1 0 !important;
    max-width: none !important;
    min-width: 0 !important;
    width: auto !important;
}
.report-date-inline .report-date-field {
    box-sizing: border-box !important;
}
.report-date-inline .report-date-field .form,
.report-date-inline .report-date-field .block,
.report-date-inline .report-date-field input {
    max-width: none !important;
    min-width: 0 !important;
    width: 100% !important;
}
#report-preview,
.report-preview {
    border-radius: 8px;
    background: #fbfcfa;
    height: calc(100vh - 260px) !important;
    max-height: calc(100vh - 260px) !important;
    min-height: 0 !important;
    box-sizing: border-box;
    flex: 1 1 auto !important;
    overflow-y: auto !important;
    overflow-x: hidden !important;
}
#report-preview .wrap,
.report-preview .wrap {
    min-height: 0 !important;
    box-sizing: border-box;
    padding: 18px;
    overflow: visible !important;
}
#report-preview .prose,
#report-preview .markdown,
.report-preview .prose,
.report-preview .markdown {
    overflow: visible !important;
}
.report-calendar-floating {
    position: fixed !important;
    z-index: 10000 !important;
    max-height: min(360px, calc(100vh - 24px)) !important;
    overflow-y: auto !important;
    overflow-x: hidden !important;
    overscroll-behavior: contain;
}
.report-calendar-floating button {
    position: relative;
    z-index: 10001;
}
.picker-container {
    bottom: 12px !important;
    max-height: min(420px, calc(100vh - 24px)) !important;
    max-width: calc(100vw - 24px) !important;
    overflow-x: auto !important;
    overflow-y: auto !important;
    position: fixed !important;
    top: auto !important;
    z-index: 10000 !important;
}
.report-preview h1,
.report-preview h2,
.report-preview h3 {
    color: #16201c;
}
</style>
<script>
const REPORT_MONTHS = {
    January: "1月",
    February: "2月",
    March: "3月",
    April: "4月",
    May: "5月",
    June: "6月",
    July: "7月",
    August: "8月",
    September: "9月",
    October: "10月",
    November: "11月",
    December: "12月",
};
const REPORT_WEEKDAYS = {Su: "日", Mo: "一", Tu: "二", We: "三", Th: "四", Fr: "五", Sa: "六"};
const REPORT_DATE_ACTIONS = {Clear: "清除", Now: "今天", Done: "完成"};

function localizeReportCalendars() {
    document.querySelectorAll("*").forEach((node) => {
        if (node.children.length > 0) return;
        const text = node.textContent.trim();
        const monthMatch = text.match(
            /^(January|February|March|April|May|June|July|August|September|October|November|December)\\s+(\\d{4})$/,
        );
        if (monthMatch) {
            node.textContent = `${monthMatch[2]}年${REPORT_MONTHS[monthMatch[1]]}`;
        } else if (REPORT_WEEKDAYS[text]) {
            node.textContent = REPORT_WEEKDAYS[text];
        } else if (REPORT_DATE_ACTIONS[text]) {
            node.textContent = REPORT_DATE_ACTIONS[text];
        }
    });
}

function findReportCalendarRoots() {
    return [...document.querySelectorAll(".picker-container")].filter(
        (node) => node instanceof HTMLElement,
    );
}

function fitReportCalendarsToViewport() {
    findReportCalendarRoots().forEach((calendar) => {
        const rect = calendar.getBoundingClientRect();
        if (rect.width < 180 || rect.height < 180) return;
        calendar.classList.add("report-calendar-floating");
        const fittedRect = calendar.getBoundingClientRect();
        const width = Math.min(fittedRect.width, window.innerWidth - 24);
        const height = Math.min(fittedRect.height, window.innerHeight - 24, 360);
        const left = Math.max(12, Math.min(fittedRect.left, window.innerWidth - width - 12));
        const top = Math.max(12, Math.min(fittedRect.top, window.innerHeight - height - 12));
        calendar.style.maxWidth = `${width}px`;
        calendar.style.left = `${left}px`;
        calendar.style.top = `${top}px`;
        calendar.style.maxHeight = `${height}px`;
    });
}

function refreshReportDatePanels() {
    fitReportCalendarsToViewport();
    localizeReportCalendars();
}

new MutationObserver(refreshReportDatePanels).observe(document.documentElement, {
    childList: true,
    subtree: true,
    characterData: true,
});
window.addEventListener("load", refreshReportDatePanels);
window.addEventListener("resize", refreshReportDatePanels);
window.addEventListener("click", () => setTimeout(refreshReportDatePanels, 0));
</script>
"""


def build_gradio_app() -> gr.Blocks:
    """构建 GitHub Sentinel 的 Gradio 可视化界面。"""
    default_start_date, default_end_date = default_week_date_range()
    with gr.Blocks(title="GitHub Sentinel Dashboard", fill_height=True) as ui:
        gr.HTML("", head=REPORT_PREVIEW_HEAD)
        gr.Markdown("# GitHub Sentinel Dashboard")

        with gr.Tab("订阅仓库"):
            with gr.Row():
                repository_url = gr.Textbox(label="仓库地址", placeholder="https://github.com/owner/repo")
                interval_seconds = gr.Number(label="订阅间隔（秒）", value=86400, precision=0)
            with gr.Row():
                access_token = gr.Textbox(label="访问令牌（可选）", type="password")
                notification_channel = gr.Textbox(label="通知通道（可选）")
            with gr.Row():
                create_button = gr.Button("创建订阅", variant="primary")
                refresh_button = gr.Button("刷新订阅")
            subscription_status = gr.Markdown()
            subscriptions_table = gr.Dataframe(
                headers=[
                    "ID",
                    "平台",
                    "仓库",
                    "间隔秒数",
                    "Token",
                    "上次运行",
                    "下次运行",
                    "状态",
                    "操作",
                ],
                datatype=["number", "str", "str", "number", "str", "str", "str", "str", "str"],
                interactive=False,
                label="订阅列表",
            )

        with gr.Tab("报告中心"):
            gr.Markdown("## 报告中心")
            with gr.Row(elem_classes=["report-center-shell"]):
                with gr.Column(scale=1, min_width=400, elem_classes=["report-controls"]):
                    subscription_select = gr.Dropdown(
                        label="选择订阅仓库",
                        choices=[],
                        allow_custom_value=True,
                    )
                    with gr.Group(elem_classes=["report-action-section"]):
                        with gr.Row(elem_classes=["report-select-row"]):
                            report_select = gr.Dropdown(
                                label="选择报告",
                                choices=[],
                                scale=4,
                                allow_custom_value=True,
                            )
                            query_reports_button = gr.Button(
                                "查询",
                                variant="primary",
                                scale=0,
                                min_width=92,
                                elem_classes=["report-query-button"],
                            )
                        report_window = gr.Dropdown(
                            label="报告列表范围",
                            choices=REPORT_WINDOW_CHOICES,
                            value="7d",
                        )
                        with gr.Row(visible=False, elem_classes=["report-date-inline"]) as query_date_row:
                            query_start_date = gr.DateTime(
                                label="开始日期",
                                value=default_start_date.isoformat(),
                                info="请选择开始日期",
                                include_time=False,
                                type="datetime",
                                timezone="Asia/Shanghai",
                                scale=1,
                                min_width=0,
                                elem_classes=["report-date-field"],
                            )
                            query_end_date = gr.DateTime(
                                label="结束日期",
                                value=default_end_date.isoformat(),
                                info="请选择结束日期",
                                include_time=False,
                                type="datetime",
                                timezone="Asia/Shanghai",
                                scale=1,
                                min_width=0,
                                elem_classes=["report-date-field"],
                            )
                    with gr.Group(elem_classes=["report-generate-section"]):
                        with gr.Row(elem_classes=["report-date-inline"]):
                            generate_start_date = gr.DateTime(
                                label="生成开始日期",
                                value=default_start_date.isoformat(),
                                info="请选择生成开始日期",
                                include_time=False,
                                type="datetime",
                                timezone="Asia/Shanghai",
                                scale=1,
                                min_width=0,
                                elem_classes=["report-date-field"],
                            )
                            generate_end_date = gr.DateTime(
                                label="生成结束日期",
                                value=default_end_date.isoformat(),
                                info="请选择生成结束日期",
                                include_time=False,
                                type="datetime",
                                timezone="Asia/Shanghai",
                                scale=1,
                                min_width=0,
                                elem_classes=["report-date-field"],
                            )
                        generate_button = gr.Button("生成报告", variant="primary")
                    operation_status = gr.Markdown()
                with gr.Column(scale=2, min_width=520, elem_classes=["report-preview-column"]):
                    report_generated_at = gr.Markdown("报告生成时间：未选择报告")
                    report_markdown = gr.Markdown(
                        label="简报预览",
                        value="请选择左侧报告后查看内容。",
                        buttons=["copy"],
                        container=True,
                        padding=True,
                        elem_id="report-preview",
                        elem_classes=["report-preview"],
                    )

        ui.load(
            refresh_subscriptions_for_ui,
            outputs=[
                subscription_status,
                subscriptions_table,
                subscription_select,
            ],
        )
        refresh_button.click(
            refresh_subscriptions_for_ui,
            outputs=[
                subscription_status,
                subscriptions_table,
                subscription_select,
            ],
        )
        create_button.click(
            create_subscription_from_ui,
            inputs=[repository_url, access_token, interval_seconds, notification_channel],
            outputs=[
                subscription_status,
                subscriptions_table,
                subscription_select,
            ],
        )
        subscriptions_table.select(
            delete_subscription_from_table,
            inputs=[subscriptions_table],
            outputs=[
                subscription_status,
                subscriptions_table,
                subscription_select,
                report_select,
                report_generated_at,
                report_markdown,
            ],
        )
        generate_button.click(
            generate_report_from_ui,
            inputs=[subscription_select, generate_start_date, generate_end_date],
            outputs=[operation_status, report_select, report_generated_at, report_markdown],
        )
        query_reports_button.click(
            load_reports_for_ui,
            inputs=[subscription_select, report_window, query_start_date, query_end_date],
            outputs=[report_select, report_generated_at, report_markdown, operation_status],
        )
        subscription_select.change(
            load_reports_for_ui,
            inputs=[subscription_select, report_window, query_start_date, query_end_date],
            outputs=[report_select, report_generated_at, report_markdown, operation_status],
        )
        report_window.change(
            toggle_custom_report_window,
            inputs=[report_window],
            outputs=[query_date_row],
        )
        report_select.change(
            load_report_content_for_ui,
            inputs=[report_select, subscription_select],
            outputs=[report_generated_at, report_markdown],
        )

    return ui


async def refresh_subscriptions_for_ui():
    """刷新订阅列表和订阅选择器。"""
    subscriptions = await _list_subscriptions()
    return (
        f"当前共有 {len(subscriptions)} 个订阅。",
        format_subscription_rows(subscriptions),
        gr.update(choices=format_subscription_choices(subscriptions), value=None),
    )


async def create_subscription_from_ui(
    repository_url: str,
    access_token: str | None,
    interval_seconds: int | float | None,
    notification_channel: str | None,
):
    """根据页面输入创建订阅。"""
    try:
        payload = SubscriptionCreate(
            repository_url=repository_url,
            access_token=_optional_text(access_token),
            interval_seconds=int(interval_seconds or 86400),
            notification_channel=_optional_text(notification_channel),
        )
        async with AsyncSessionLocal() as session:
            await create_subscription(session, payload)
        subscriptions = await _list_subscriptions()
        return (
            "订阅创建成功。",
            format_subscription_rows(subscriptions),
            gr.update(choices=format_subscription_choices(subscriptions), value=None),
        )
    except (ApiError, ValueError) as exc:
        subscriptions = await _list_subscriptions()
        return (
            _error_message(exc),
            format_subscription_rows(subscriptions),
            gr.update(choices=format_subscription_choices(subscriptions), value=None),
        )


async def generate_report_from_ui(
    subscription_id: int | None,
    start_date: str | datetime | date | None,
    end_date: str | datetime | date | None,
):
    """按页面选择的日期范围生成报告。"""
    if subscription_id is None:
        return (
            "请先选择订阅仓库。",
            gr.update(choices=[], value=None),
            "报告生成时间：未选择报告",
            "请选择左侧报告后查看内容。",
        )
    try:
        if start_date is None or end_date is None:
            raise ValueError("请先选择开始日期和结束日期。")
        parsed_start = parse_ui_date(start_date)
        parsed_end = parse_ui_date(end_date)
        if parsed_end < parsed_start:
            raise ValueError("结束日期必须大于或等于开始日期。")
        async with AsyncSessionLocal() as session:
            _, report = await build_sentinel_agent().generate_report_for_date_range(
                session,
                int(subscription_id),
                parsed_start,
                parsed_end,
            )
        reports = await _list_reports(int(subscription_id))
        return (
            f"报告生成成功：{report.name}",
            gr.update(choices=format_report_choices(reports), value=report.id),
            _format_report_generated_at(report),
            report.content_markdown,
        )
    except (ApiError, ValueError) as exc:
        reports = await _list_reports(int(subscription_id))
        return (
            _error_message(exc),
            gr.update(choices=format_report_choices(reports), value=None),
            "报告生成时间：未选择报告",
            "请选择左侧报告后查看内容。",
        )


async def load_reports_for_ui(
    subscription_id: int | None,
    report_window: str | None,
    start_date: str | datetime | date | None,
    end_date: str | datetime | date | None,
):
    """加载指定订阅绑定的报告。"""
    if subscription_id is None:
        return (
            gr.update(choices=[], value=None),
            "报告生成时间：未选择报告",
            "请选择左侧报告后查看内容。",
            "请先选择订阅仓库。",
        )
    try:
        generated_since, generated_before = _resolve_report_window(report_window, start_date, end_date)
    except ValueError as exc:
        return (
            gr.update(choices=[], value=None),
            "报告生成时间：未选择报告",
            "请选择左侧报告后查看内容。",
            _error_message(exc),
        )
    reports = await _list_reports(
        int(subscription_id),
        generated_since=generated_since,
        generated_before=generated_before,
    )
    return (
        gr.update(choices=format_report_choices(reports), value=None),
        "报告生成时间：未选择报告",
        "请选择左侧报告后查看内容。",
        f"查询完成：共 {len(reports)} 份报告。",
    )


async def load_report_content_for_ui(
    report_id: int | str | None,
    subscription_id: int | str | None,
) -> tuple[str, str]:
    """加载选中的 Markdown 报告正文。"""
    if report_id in (None, "") or subscription_id in (None, ""):
        return "报告生成时间：未选择报告", "请选择左侧报告后查看内容。"
    selected_report_id = int(report_id)
    reports = await _list_reports(int(subscription_id))
    for report in reports:
        if report.id == selected_report_id:
            return _format_report_generated_at(report), report.content_markdown
    return "报告生成时间：未选择报告", "请选择左侧报告后查看内容。"


async def delete_subscription_from_table(rows: list[list[object]] | None, evt: gr.SelectData):
    """点击订阅列表最右侧操作列时删除对应订阅。"""
    subscription_id = _selected_delete_subscription_id(rows, evt)
    if subscription_id is None:
        subscriptions = await _list_subscriptions()
        return (
            "请点击订阅列表最右侧的删除操作。",
            format_subscription_rows(subscriptions),
            gr.update(choices=format_subscription_choices(subscriptions), value=None),
            gr.update(choices=[], value=None),
            "报告生成时间：未选择报告",
            "请选择左侧报告后查看内容。",
        )
    return await delete_subscription_from_ui(subscription_id)


async def delete_subscription_from_ui(subscription_id: int | None):
    """删除当前选中的订阅并刷新页面数据。"""
    if subscription_id is not None:
        async with AsyncSessionLocal() as session:
            await delete_subscription(session, int(subscription_id))
    subscriptions = await _list_subscriptions()
    return (
        "订阅已删除。" if subscription_id is not None else "请先选择订阅仓库。",
        format_subscription_rows(subscriptions),
        gr.update(choices=format_subscription_choices(subscriptions), value=None),
        gr.update(choices=[], value=None),
        "报告生成时间：未选择报告",
        "请选择左侧报告后查看内容。",
    )


def parse_ui_date(value: str | datetime | date | None) -> date:
    """解析页面输入的日期字符串。"""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value is None:
        raise ValueError("日期格式必须为 YYYY-MM-DD。")
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise ValueError("日期格式必须为 YYYY-MM-DD。") from exc


def default_week_date_range() -> tuple[date, date]:
    """返回页面默认展示的最近一周日期范围。"""
    end_date = report_now().date()
    return end_date - timedelta(days=7), end_date


def format_subscription_choices(subscriptions: list[Subscription]) -> list[tuple[str, int]]:
    """格式化订阅下拉选择项。"""
    return [
        (f"#{subscription.id} {subscription.platform} {subscription.owner}/{subscription.repo}", subscription.id)
        for subscription in subscriptions
    ]


def format_report_choices(reports: list[Report]) -> list[tuple[str, int]]:
    """格式化报告下拉选择项。"""
    return [
        (f"{_report_repo_name(report)}（{_report_period_label(report)}）", report.id)
        for report in reports
    ]


def format_subscription_rows(subscriptions: list[Subscription]) -> list[list[object]]:
    """格式化订阅表格行。"""
    return [
        [
            subscription.id,
            subscription.platform,
            f"{subscription.owner}/{subscription.repo}",
            subscription.interval_seconds,
            "已配置" if subscription.token_configured else "未配置",
            _format_optional_datetime(subscription.last_run_at),
            _format_optional_datetime(subscription.next_run_at),
            "启用" if subscription.is_active else "停用",
            "删除",
        ]
        for subscription in subscriptions
    ]


def toggle_custom_report_window(report_window: str | None):
    """按报告范围选择控制自定义日期输入是否显示。"""
    return gr.update(visible=report_window == "custom")


async def _list_subscriptions() -> list[Subscription]:
    async with AsyncSessionLocal() as session:
        return await list_subscriptions(session)


async def _list_reports(
    subscription_id: int,
    generated_since: datetime | None = None,
    generated_before: datetime | None = None,
) -> list[Report]:
    async with AsyncSessionLocal() as session:
        return await list_reports(
            session,
            subscription_id=subscription_id,
            generated_since=generated_since,
            generated_before=generated_before,
        )


def _resolve_report_window(
    report_window: str | None,
    start_date: str | datetime | date | None,
    end_date: str | datetime | date | None,
) -> tuple[datetime | None, datetime | None]:
    now = report_now()
    if report_window == "custom":
        if start_date is None or end_date is None:
            raise ValueError("请选择报告列表范围的开始日期和结束日期。")
        start = parse_ui_date(start_date)
        end = parse_ui_date(end_date)
        if end < start:
            raise ValueError("报告列表范围的结束日期必须大于或等于开始日期。")
        return datetime.combine(start, datetime.min.time()), datetime.combine(
            end + timedelta(days=1),
            datetime.min.time(),
        )
    days = {"1d": 1, "3d": 3, "5d": 5, "7d": 7, "30d": 30}.get(report_window or "1d", 1)
    return now - timedelta(days=days), None


def _report_repo_name(report: Report) -> str:
    subscription = report.subscription
    if subscription is not None:
        return subscription.repo

    if report.period_start_date is not None and report.period_end_date is not None:
        suffix = f"_{report.period_start_date.isoformat()}_{report.period_end_date.isoformat()}"
        base = report.name.removesuffix(suffix)
    else:
        base = report.name.rsplit("_", 1)[0]
    if base == report.name:
        base = report.name.rsplit("_", 1)[0]
    return base.split("_")[-1] if "_" in base else base


def _report_period_label(report: Report) -> str:
    if report.period_start_date is not None and report.period_end_date is not None:
        return f"{report.period_start_date.isoformat()}~{report.period_end_date.isoformat()}"
    return format_report_datetime(report.generated_at).split(" ")[0]


def _format_report_generated_at(report: Report) -> str:
    return f"报告生成时间：{format_report_datetime(report.generated_at)}"


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _format_optional_datetime(value: datetime | None) -> str:
    if value is None:
        return ""
    return format_report_datetime(value)


def _selected_delete_subscription_id(rows: object | None, evt: gr.SelectData) -> int | None:
    if rows is None or evt.index is None:
        return None
    row_index, column_index = evt.index
    if column_index != 8 or row_index >= len(rows):
        return None
    if hasattr(rows, "iloc"):
        return int(rows.iloc[row_index, 0])
    return int(rows[row_index][0])


def _error_message(exc: Exception) -> str:
    if isinstance(exc, ApiError):
        return exc.message
    return str(exc)
