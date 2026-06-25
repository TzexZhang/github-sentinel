"""Gradio 可视化界面。"""

from datetime import date, datetime, timedelta

import gradio as gr

from app.api.deps import build_notification_router, build_sentinel_agent
from app.core.config import settings
from app.core.errors import ApiError
from app.db.models import Report, Subscription
from app.db.session import AsyncSessionLocal
from app.repositories.reports import batch_delete_reports, list_reports
from app.repositories.users import get_user_by_session_token
from app.repositories.subscriptions import (
    create_subscription,
    delete_subscription,
    get_subscription,
    list_subscriptions,
    update_subscription,
)
from app.schemas.subscriptions import (
    SubscriptionCreate,
    SubscriptionUpdate,
    normalize_notification_channel_name,
    validate_notification_channel_target,
)
from app.services.time_utils import format_report_datetime
from app.services.time_utils import report_now
from app.services.notification_worker import NotificationWorker

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
const RUNTIME_INSTANCE_STORAGE_KEY = "git-sentinel-runtime-instance-id";
// 后端热重载轮询开关：仅开发模式（DEBUG=true）启用，避免生产环境的无意义轮询。
// 占位符由后端在构建页面时替换为 true / false。
const RUNTIME_POLLING_ENABLED = __RUNTIME_POLLING_ENABLED__;

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

async function refreshPageAfterBackendReload() {
    try {
        const response = await fetch("/api/runtime", {cache: "no-store"});
        if (!response.ok) return;
        const payload = await response.json();
        const instanceId = payload.instance_id;
        if (!instanceId) return;
        const storedInstanceId = sessionStorage.getItem(RUNTIME_INSTANCE_STORAGE_KEY);
        if (!storedInstanceId) {
            sessionStorage.setItem(RUNTIME_INSTANCE_STORAGE_KEY, instanceId);
            return;
        }
        if (storedInstanceId !== instanceId) {
            sessionStorage.setItem(RUNTIME_INSTANCE_STORAGE_KEY, instanceId);
            window.location.reload();
        }
    } catch {
        // 服务热重载过程中会短暂不可用，下一轮轮询成功后再刷新页面。
    }
}

async function postJson(url, payload) {
    const response = await fetch(url, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload),
    });
    let data = {};
    try {
        data = await response.json();
    } catch {
        data = {};
    }
    if (!response.ok) {
        throw new Error(data.data?.message || "请求失败。");
    }
    return data;
}

function bindUserManagementPanel() {
    const root = document.getElementById("user-management-panel");
    if (!root || root.dataset.bound === "true") return;
    root.dataset.bound = "true";
    const userInfo = root.querySelector("[data-user-info]");
    const status = root.querySelector("[data-user-status]");
    const oldPassword = root.querySelector("[data-old-password]");
    const newPassword = root.querySelector("[data-new-password]");
    const confirmPassword = root.querySelector("[data-confirm-password]");
    fetch("/api/auth/me")
        .then((response) => response.ok ? response.json() : null)
        .then((payload) => {
            if (payload?.data?.username) {
                userInfo.textContent = `当前用户：${payload.data.username}`;
            }
        })
        .catch(() => {});
    root.querySelector("[data-change-password]").addEventListener("click", async () => {
        status.textContent = "";
        status.className = "user-management-status";
        if (newPassword.value !== confirmPassword.value) {
            status.textContent = "两次输入的新密码不一致。";
            return;
        }
        try {
            await postJson("/api/auth/change-password", {
                old_password: oldPassword.value,
                new_password: newPassword.value,
            });
            oldPassword.value = "";
            newPassword.value = "";
            confirmPassword.value = "";
            status.className = "user-management-status success";
            status.textContent = "密码修改成功。";
        } catch (error) {
            status.textContent = error.message || "密码修改失败。";
        }
    });
    root.querySelector("[data-logout]").addEventListener("click", async () => {
        await fetch("/api/auth/logout", {method: "POST"});
        window.location.href = "/login";
    });
}

new MutationObserver(refreshReportDatePanels).observe(document.documentElement, {
    childList: true,
    subtree: true,
    characterData: true,
});
window.addEventListener("load", refreshReportDatePanels);
window.addEventListener("load", bindUserManagementPanel);
window.addEventListener("click", () => setTimeout(bindUserManagementPanel, 0));
window.addEventListener("resize", refreshReportDatePanels);
window.addEventListener("click", () => setTimeout(refreshReportDatePanels, 0));
if (RUNTIME_POLLING_ENABLED) {
    window.addEventListener("load", refreshPageAfterBackendReload);
    window.setInterval(refreshPageAfterBackendReload, 1500);
}
</script>
"""

USER_MANAGEMENT_HTML = """
<style>
.user-management-panel {
    border: 1px solid #dde5df;
    border-radius: 8px;
    background: #fbfcfa;
    padding: 16px;
    max-width: 520px;
}
.user-management-panel label {
    display: grid;
    gap: 6px;
    margin-bottom: 12px;
}
.user-management-panel input {
    min-height: 38px;
    border: 1px solid #d7ded9;
    border-radius: 6px;
    padding: 8px 10px;
}
.user-management-actions {
    display: flex;
    gap: 10px;
    margin-top: 8px;
}
.user-management-actions button {
    min-height: 38px;
    border: 1px solid #2f6b4f;
    border-radius: 6px;
    padding: 0 14px;
    background: #2f6b4f;
    color: #fff;
    cursor: pointer;
}
.user-management-actions button.secondary {
    background: #fff;
    color: #2f6b4f;
}
.user-management-status {
    min-height: 22px;
    margin-top: 12px;
    color: #8f1d1d;
}
.user-management-status.success {
    color: #187b58;
}
</style>
<div class="user-management-panel" id="user-management-panel">
  <p data-user-info>当前用户：加载中...</p>
  <label>当前密码<input data-old-password type="password" autocomplete="current-password"></label>
  <label>新密码（6-12 位）<input data-new-password type="password" minlength="6" maxlength="12" autocomplete="new-password"></label>
  <label>确认新密码<input data-confirm-password type="password" minlength="6" maxlength="12" autocomplete="new-password"></label>
  <div class="user-management-actions">
    <button type="button" data-change-password>修改密码</button>
    <button type="button" class="secondary" data-logout>退出登录</button>
  </div>
  <div class="user-management-status" data-user-status></div>
</div>
"""


def build_gradio_app() -> gr.Blocks:
    """构建 Git Sentinel 的 Gradio 可视化界面。"""
    default_start_date, default_end_date = default_week_date_range()
    # 仅开发模式启用前端热重载轮询，生产环境替换为 false 以避免无意义轮询请求。
    dashboard_head = REPORT_PREVIEW_HEAD.replace(
        "__RUNTIME_POLLING_ENABLED__",
        "true" if settings.debug else "false",
    )
    with gr.Blocks(title="Git Sentinel Dashboard", fill_height=True) as ui:
        gr.HTML("", head=dashboard_head)
        gr.Markdown("# Git Sentinel Dashboard")
        editing_subscription_id = gr.State(None)

        with gr.Tab("订阅仓库"):
            with gr.Row():
                repository_url = gr.Textbox(label="仓库地址", placeholder="https://github.com/owner/repo")
                interval_seconds = gr.Number(label="订阅间隔（秒）", value=86400, precision=0)
            with gr.Row():
                access_token = gr.Textbox(label="访问令牌（可选）", type="password")
                notification_channel_type = gr.Dropdown(
                    label="通知类型",
                    choices=[
                        ("不通知", ""),
                        ("邮箱 SMTP", "smtp"),
                        ("企业微信通知", "wecom"),
                    ],
                    value="smtp",
                )
            notification_channel_target = gr.Textbox(
                label="通知目标（可选）",
                placeholder="邮箱填写收件人地址；企业微信填写成员账号或目标标识",
            )
            with gr.Row():
                create_button = gr.Button("创建订阅", variant="primary")
                update_button = gr.Button("保存修改", visible=False)
                delete_button = gr.Button("删除订阅", visible=False)
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
                        send_notification_after_generate = gr.Checkbox(
                            label="生成后发送通知",
                            value=False,
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

        with gr.Tab("报告管理"):
            gr.Markdown("## 报告管理")
            report_management_status = gr.Markdown()
            report_management_choices = gr.CheckboxGroup(
                label="勾选要删除的报告",
                choices=[],
                interactive=True,
            )
            with gr.Row():
                refresh_report_management_button = gr.Button("刷新管理列表")
                select_all_reports_button = gr.Button("全部勾选")
                clear_report_selection_button = gr.Button("取消勾选")
                delete_reports_button = gr.Button("删除选中报告", variant="stop")

        with gr.Tab("用户管理"):
            gr.Markdown("## 用户管理")
            gr.HTML(USER_MANAGEMENT_HTML)

        ui.load(
            refresh_subscriptions_for_ui,
            outputs=[
                subscription_status,
                subscriptions_table,
                subscription_select,
            ],
            queue=False,
        )
        ui.load(
            refresh_report_management_for_ui,
            outputs=[report_management_status, report_management_choices],
            queue=False,
        )
        refresh_button.click(
            refresh_subscriptions_for_ui,
            outputs=[
                subscription_status,
                subscriptions_table,
                subscription_select,
            ],
            queue=False,
        )
        subscription_form_outputs = [
            repository_url,
            access_token,
            interval_seconds,
            notification_channel_type,
            notification_channel_target,
            editing_subscription_id,
            create_button,
            update_button,
            delete_button,
        ]
        create_button.click(
            create_subscription_from_ui,
            inputs=[
                repository_url,
                access_token,
                interval_seconds,
                notification_channel_type,
                notification_channel_target,
            ],
            outputs=[
                subscription_status,
                subscriptions_table,
                subscription_select,
                *subscription_form_outputs,
            ],
            queue=False,
        )
        subscriptions_table.select(
            handle_subscription_table_action,
            inputs=[subscriptions_table],
            outputs=[
                subscription_status,
                subscriptions_table,
                subscription_select,
                report_select,
                report_generated_at,
                report_markdown,
                *subscription_form_outputs,
            ],
            queue=False,
        )
        update_button.click(
            update_subscription_from_ui,
            inputs=[
                editing_subscription_id,
                interval_seconds,
                notification_channel_type,
                notification_channel_target,
            ],
            outputs=[
                subscription_status,
                subscriptions_table,
                subscription_select,
                *subscription_form_outputs,
            ],
            queue=False,
        )
        delete_button.click(
            delete_subscription_from_ui,
            inputs=[editing_subscription_id],
            outputs=[
                subscription_status,
                subscriptions_table,
                subscription_select,
                report_select,
                report_generated_at,
                report_markdown,
                *subscription_form_outputs,
                report_management_status,
                report_management_choices,
            ],
            queue=False,
        )
        generate_button.click(
            generate_report_from_ui,
            inputs=[
                subscription_select,
                generate_start_date,
                generate_end_date,
                send_notification_after_generate,
            ],
            outputs=[operation_status, report_select, report_generated_at, report_markdown],
            queue=False,
        )
        query_reports_button.click(
            load_reports_for_ui,
            inputs=[subscription_select, report_window, query_start_date, query_end_date],
            outputs=[report_select, report_generated_at, report_markdown, operation_status],
            queue=False,
        )
        subscription_select.change(
            load_reports_for_ui,
            inputs=[subscription_select, report_window, query_start_date, query_end_date],
            outputs=[report_select, report_generated_at, report_markdown, operation_status],
            queue=False,
        )
        report_window.change(
            toggle_custom_report_window,
            inputs=[report_window],
            outputs=[query_date_row],
            queue=False,
        )
        report_select.change(
            load_report_content_for_ui,
            inputs=[report_select, subscription_select],
            outputs=[report_generated_at, report_markdown],
            queue=False,
        )
        refresh_report_management_button.click(
            refresh_report_management_for_ui,
            outputs=[report_management_status, report_management_choices],
            queue=False,
        )
        select_all_reports_button.click(
            select_all_report_management_for_ui,
            outputs=[report_management_choices],
            queue=False,
        )
        clear_report_selection_button.click(
            clear_report_management_selection,
            outputs=[report_management_choices],
            queue=False,
        )
        delete_reports_button.click(
            delete_reports_from_ui,
            inputs=[report_management_choices],
            outputs=[report_management_status, report_management_choices],
            queue=False,
        )

    return ui


async def refresh_subscriptions_for_ui(request: gr.Request):
    """刷新订阅列表和订阅选择器。"""
    user_id = await _current_user_id_from_request(request)
    if user_id is None:
        return (
            "请重新登录后查看订阅。",
            [],
            gr.update(choices=[], value=None),
        )
    subscriptions = await _list_subscriptions(user_id)
    return (
        f"当前共有 {len(subscriptions)} 个订阅。",
        format_subscription_rows(subscriptions),
        gr.update(choices=format_subscription_choices(subscriptions), value=None),
    )


async def refresh_report_management_for_ui(request: gr.Request):
    """刷新报告管理列表。"""
    user_id = await _current_user_id_from_request(request)
    if user_id is None:
        return "请重新登录后查看报告。", gr.update(choices=[], value=[])
    reports = await _list_reports(user_id=user_id)
    return (
        f"当前共有 {len(reports)} 份报告。",
        gr.update(choices=format_report_management_choices(reports), value=[]),
    )


async def select_all_report_management_for_ui(request: gr.Request):
    """勾选当前用户可见的全部报告。"""
    user_id = await _current_user_id_from_request(request)
    if user_id is None:
        return gr.update(value=[])
    reports = await _list_reports(user_id=user_id)
    return gr.update(value=[report.id for report in reports])


def clear_report_management_selection():
    """清空报告管理列表中的勾选项。"""
    return gr.update(value=[])


async def delete_reports_from_ui(report_ids: list[int | str] | None, request: gr.Request):
    """批量物理删除用户勾选的报告。"""
    user_id = await _current_user_id_from_request(request)
    if user_id is None:
        return "请重新登录后删除报告。", gr.update(choices=[], value=[])
    selected_ids = [int(report_id) for report_id in (report_ids or [])]
    if not selected_ids:
        reports = await _list_reports(user_id=user_id)
        return (
            "请先勾选要删除的报告。",
            gr.update(choices=format_report_management_choices(reports), value=[]),
        )
    async with AsyncSessionLocal() as session:
        deleted_count, not_found_ids = await batch_delete_reports(session, selected_ids, user_id=user_id)
    reports = await _list_reports(user_id=user_id)
    status = f"已删除 {deleted_count} 份报告。"
    if not_found_ids:
        status = f"{status} 未找到或无权限删除：{', '.join(str(report_id) for report_id in not_found_ids)}。"
    return (
        status,
        gr.update(choices=format_report_management_choices(reports), value=[]),
    )


async def create_subscription_from_ui(
    repository_url: str,
    access_token: str | None,
    interval_seconds: int | float | None,
    notification_channel_type: str | None,
    notification_channel_target: str | None,
    request: gr.Request,
):
    """根据页面输入创建订阅。"""
    user_id = await _current_user_id_from_request(request)
    if user_id is None:
        return (
            "请重新登录后创建订阅。",
            [],
            gr.update(choices=[], value=None),
            *_subscription_form_output_values(_subscription_form_noop_updates()),
        )
    try:
        payload = SubscriptionCreate(
            repository_url=repository_url,
            access_token=_optional_text(access_token),
            interval_seconds=int(interval_seconds or 86400),
            notification_channels=_notification_channels_from_ui(
                notification_channel_type,
                notification_channel_target,
            ),
        )
        async with AsyncSessionLocal() as session:
            await create_subscription(session, payload, user_id=user_id)
        subscriptions = await _list_subscriptions(user_id)
        return (
            "订阅创建成功。",
            format_subscription_rows(subscriptions),
            gr.update(choices=format_subscription_choices(subscriptions), value=None),
            *_subscription_form_output_values(_empty_subscription_form_updates()),
        )
    except (ApiError, ValueError) as exc:
        subscriptions = await _list_subscriptions(user_id)
        return (
            _error_message(exc),
            format_subscription_rows(subscriptions),
            gr.update(choices=format_subscription_choices(subscriptions), value=None),
            *_subscription_form_output_values(_subscription_form_noop_updates()),
        )


async def update_subscription_from_ui(
    subscription_id: int | None,
    interval_seconds: int | float | None,
    notification_channel_type: str | None,
    notification_channel_target: str | None,
    request: gr.Request,
):
    """根据页面输入更新订阅间隔和通知配置。"""
    user_id = await _current_user_id_from_request(request)
    if user_id is None:
        return (
            "请重新登录后修改订阅。",
            [],
            gr.update(choices=[], value=None),
            *_subscription_form_output_values(_subscription_form_noop_updates()),
        )
    if subscription_id is None:
        subscriptions = await _list_subscriptions(user_id)
        return (
            "请先在订阅列表点击“修改”。",
            format_subscription_rows(subscriptions),
            gr.update(choices=format_subscription_choices(subscriptions), value=None),
            *_subscription_form_output_values(_empty_subscription_form_updates()),
        )
    try:
        payload = SubscriptionUpdate(
            interval_seconds=int(interval_seconds or 86400),
            notification_channels=_notification_channels_from_ui(
                notification_channel_type,
                notification_channel_target,
            ),
        )
        async with AsyncSessionLocal() as session:
            await update_subscription(session, int(subscription_id), payload, user_id=user_id)
        subscriptions = await _list_subscriptions(user_id)
        return (
            "订阅修改成功。",
            format_subscription_rows(subscriptions),
            gr.update(choices=format_subscription_choices(subscriptions), value=None),
            *_subscription_form_output_values(_empty_subscription_form_updates()),
        )
    except (ApiError, ValueError) as exc:
        subscriptions = await _list_subscriptions(user_id)
        return (
            _error_message(exc),
            format_subscription_rows(subscriptions),
            gr.update(choices=format_subscription_choices(subscriptions), value=None),
            *_subscription_form_output_values(_subscription_form_noop_updates()),
        )


async def generate_report_from_ui(
    subscription_id: int | None,
    start_date: str | datetime | date | None,
    end_date: str | datetime | date | None,
    send_notification: bool | None = False,
    request: gr.Request | None = None,
):
    """按页面选择的日期范围生成报告。"""
    user_id = await _current_user_id_from_request(request)
    if user_id is None:
        return (
            "请重新登录后生成报告。",
            gr.update(choices=[], value=None),
            "报告生成时间：未选择报告",
            "请选择左侧报告后查看内容。",
        )
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
            if await get_subscription(session, int(subscription_id), user_id=user_id) is None:
                raise ApiError(status_code=404, code="subscription_not_found", message="订阅不存在。")
            result, report = await build_sentinel_agent().generate_report_for_date_range(
                session,
                int(subscription_id),
                parsed_start,
                parsed_end,
                send_notification=bool(send_notification),
            )
        reports = await _list_reports(int(subscription_id), user_id=user_id)
        status = f"报告生成成功：{report.name}"
        if send_notification:
            worker_result = (
                await _dispatch_pending_notifications_once()
                if result.notification_sent
                else None
            )
            status = (
                f"报告生成成功并已发送通知：{report.name}"
                if worker_result is not None and worker_result.sent > 0
                else f"报告生成成功并已加入通知队列：{report.name}"
                if result.notification_sent
                else f"报告生成成功，但该订阅没有启用通知通道：{report.name}"
            )
        return (
            status,
            gr.update(choices=format_report_choices(reports), value=report.id),
            _format_report_generated_at(report),
            report.content_markdown,
        )
    except (ApiError, ValueError) as exc:
        reports = await _list_reports(int(subscription_id), user_id=user_id)
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
    request: gr.Request | None = None,
):
    """加载指定订阅绑定的报告。"""
    user_id = await _current_user_id_from_request(request)
    if user_id is None:
        return (
            gr.update(choices=[], value=None),
            "报告生成时间：未选择报告",
            "请选择左侧报告后查看内容。",
            "请重新登录后查看报告。",
        )
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
        user_id=user_id,
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
    request: gr.Request | None = None,
) -> tuple[str, str]:
    """加载选中的 Markdown 报告正文。"""
    user_id = await _current_user_id_from_request(request)
    if user_id is None:
        return "报告生成时间：未选择报告", "请重新登录后查看报告。"
    if report_id in (None, "") or subscription_id in (None, ""):
        return "报告生成时间：未选择报告", "请选择左侧报告后查看内容。"
    selected_report_id = int(report_id)
    reports = await _list_reports(int(subscription_id), user_id=user_id)
    for report in reports:
        if report.id == selected_report_id:
            return _format_report_generated_at(report), report.content_markdown
    return "报告生成时间：未选择报告", "请选择左侧报告后查看内容。"


async def handle_subscription_table_action(
    rows: list[list[object]] | None,
    evt: gr.SelectData,
    request: gr.Request,
):
    """处理订阅列表中的操作列点击。"""
    user_id = await _current_user_id_from_request(request)
    if user_id is None:
        return (
            "请重新登录后修改订阅。",
            [],
            gr.update(choices=[], value=None),
            gr.update(),
            gr.update(),
            gr.update(),
            *_subscription_form_output_values(_subscription_form_noop_updates()),
        )
    subscriptions = await _list_subscriptions(user_id)

    edit_subscription_id = _selected_edit_subscription_id(rows, evt)
    if edit_subscription_id is not None:
        for subscription in subscriptions:
            if subscription.id == edit_subscription_id:
                return (
                    f"正在修改订阅：{subscription.owner}/{subscription.repo}",
                    format_subscription_rows(subscriptions),
                    gr.update(choices=format_subscription_choices(subscriptions), value=None),
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    *_subscription_form_output_values(_subscription_edit_form_updates(subscription)),
                )
        return (
            "订阅不存在。",
            format_subscription_rows(subscriptions),
            gr.update(choices=format_subscription_choices(subscriptions), value=None),
            gr.update(),
            gr.update(),
            gr.update(),
            *_subscription_form_output_values(_empty_subscription_form_updates()),
        )

    return (
        "请点击订阅列表中的操作列。",
        format_subscription_rows(subscriptions),
        gr.update(choices=format_subscription_choices(subscriptions), value=None),
        gr.update(),
        gr.update(),
        gr.update(),
        *_subscription_form_output_values(_subscription_form_noop_updates()),
    )


async def delete_subscription_from_ui(subscription_id: int | None, request: gr.Request):
    """删除当前选中的订阅并刷新页面数据。"""
    user_id = await _current_user_id_from_request(request)
    if user_id is None:
        return (
            "请重新登录后删除订阅。",
            [],
            gr.update(choices=[], value=None),
            gr.update(choices=[], value=None),
            "报告生成时间：未选择报告",
            "请选择左侧报告后查看内容。",
            *_subscription_form_output_values(_subscription_form_noop_updates()),
            "请重新登录后查看报告。",
            gr.update(choices=[], value=[]),
        )
    if subscription_id is not None:
        async with AsyncSessionLocal() as session:
            await delete_subscription(session, int(subscription_id), user_id=user_id)
    subscriptions = await _list_subscriptions(user_id)
    reports = await _list_reports(user_id=user_id)
    return (
        "订阅已删除。" if subscription_id is not None else "请先选择订阅仓库。",
        format_subscription_rows(subscriptions),
        gr.update(choices=format_subscription_choices(subscriptions), value=None),
        gr.update(choices=[], value=None),
        "报告生成时间：未选择报告",
        "请选择左侧报告后查看内容。",
        *_subscription_form_output_values(_empty_subscription_form_updates()),
        f"当前共有 {len(reports)} 份报告。",
        gr.update(choices=format_report_management_choices(reports), value=[]),
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
        (f"{subscription.owner}/{subscription.repo}", subscription.id)
        for subscription in subscriptions
    ]


def format_report_choices(reports: list[Report]) -> list[tuple[str, int]]:
    """格式化报告下拉选择项。"""
    return [
        (f"{_report_repo_name(report)}（{_report_period_label(report)}）", report.id)
        for report in reports
    ]


def format_report_management_choices(reports: list[Report]) -> list[tuple[str, int]]:
    """格式化报告管理复选项。"""
    return [
        (
            f"{_report_repo_name(report)}（{_report_period_label(report)}）"
            f" - {format_report_datetime(report.generated_at)}",
            report.id,
        )
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
            "修改 / 删除",
        ]
        for subscription in subscriptions
    ]


def toggle_custom_report_window(report_window: str | None):
    """按报告范围选择控制自定义日期输入是否显示。"""
    return gr.update(visible=report_window == "custom")


async def _current_user_id_from_request(request: gr.Request | None) -> int | None:
    if request is None:
        return None
    token = dict(getattr(request, "cookies", {})).get(settings.auth_cookie_name)
    if not token:
        return None
    async with AsyncSessionLocal() as session:
        user = await get_user_by_session_token(session, token)
        return user.id if user is not None else None


async def _list_subscriptions(user_id: int) -> list[Subscription]:
    async with AsyncSessionLocal() as session:
        return await list_subscriptions(session, user_id=user_id)


async def _list_reports(
    subscription_id: int | None = None,
    user_id: int | None = None,
    generated_since: datetime | None = None,
    generated_before: datetime | None = None,
) -> list[Report]:
    async with AsyncSessionLocal() as session:
        return await list_reports(
            session,
            subscription_id=subscription_id,
            user_id=user_id,
            generated_since=generated_since,
            generated_before=generated_before,
        )


async def _dispatch_pending_notifications_once():
    worker = NotificationWorker(
        session_factory=AsyncSessionLocal,
        notification_sender=build_notification_router(),
        tick_seconds=settings.notification_worker_tick_seconds,
    )
    return await worker.run_pending_once()


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


def _notification_channels_from_ui(
    channel_type: str | None,
    target: str | None,
) -> list[dict[str, str]]:
    normalized_type = _optional_text(channel_type)
    normalized_target = _optional_text(target)
    if normalized_type is None and normalized_target is None:
        return []
    if normalized_type is None or normalized_target is None:
        raise ValueError("通知类型和通知目标需要同时填写。")
    if normalized_type not in {"smtp", "wecom"}:
        raise ValueError("仓库订阅页面暂不支持该通知类型。")
    validate_notification_channel_target(normalized_type, normalized_target)
    return [
        {
            "name": normalize_notification_channel_name(
                normalized_type,
                normalized_target,
            ),
            "channel_type": normalized_type,
            "target": normalized_target,
        },
    ]


_SUBSCRIPTION_FORM_OUTPUT_KEYS = (
    "repository_url",
    "access_token",
    "interval_seconds",
    "notification_channel_type",
    "notification_channel_target",
    "editing_subscription_id",
    "create_button",
    "update_button",
    "delete_button",
)


def _empty_subscription_form_updates() -> dict[str, object]:
    return {
        "repository_url": gr.update(value="", interactive=True),
        "access_token": gr.update(value="", interactive=True),
        "interval_seconds": gr.update(value=86400),
        "notification_channel_type": gr.update(value="smtp"),
        "notification_channel_target": gr.update(value=""),
        "editing_subscription_id": None,
        "create_button": gr.update(visible=True),
        "update_button": gr.update(visible=False),
        "delete_button": gr.update(visible=False),
    }


def _subscription_edit_form_updates(subscription: Subscription) -> dict[str, object]:
    channel = subscription.notification_channels[0] if subscription.notification_channels else None
    return {
        "repository_url": gr.update(value=subscription.repository_url, interactive=False),
        "access_token": gr.update(value="已配置" if subscription.token_configured else "", interactive=False),
        "interval_seconds": gr.update(value=subscription.interval_seconds),
        "notification_channel_type": gr.update(value=_notification_channel_value(channel, "channel_type")),
        "notification_channel_target": gr.update(value=_notification_channel_value(channel, "target")),
        "editing_subscription_id": subscription.id,
        "create_button": gr.update(visible=False),
        "update_button": gr.update(visible=True),
        "delete_button": gr.update(visible=True),
    }


def _subscription_form_noop_updates() -> dict[str, object]:
    return {key: gr.update() for key in _SUBSCRIPTION_FORM_OUTPUT_KEYS}


def _subscription_form_output_values(updates: dict[str, object]) -> tuple[object, ...]:
    return tuple(updates[key] for key in _SUBSCRIPTION_FORM_OUTPUT_KEYS)


def _notification_channel_value(channel: object | None, key: str) -> str:
    if channel is None:
        return ""
    if isinstance(channel, dict):
        return str(channel.get(key) or "")
    return str(getattr(channel, key, "") or "")


def _format_optional_datetime(value: datetime | None) -> str:
    if value is None:
        return ""
    return format_report_datetime(value)


def _selected_delete_subscription_id(rows: object | None, evt: gr.SelectData) -> int | None:
    return None


def _selected_edit_subscription_id(rows: object | None, evt: gr.SelectData) -> int | None:
    return _selected_subscription_id_by_action_column(rows, evt, 8)


def _selected_subscription_id_by_action_column(
    rows: object | None,
    evt: gr.SelectData,
    action_column_index: int,
) -> int | None:
    if rows is None or evt.index is None:
        return None
    row_index, column_index = evt.index
    if column_index != action_column_index or row_index >= len(rows):
        return None
    if hasattr(rows, "iloc"):
        return int(rows.iloc[row_index, 0])
    return int(rows[row_index][0])


def _error_message(exc: Exception) -> str:
    if isinstance(exc, ApiError):
        return exc.message
    return str(exc)
