from datetime import date, datetime

import pytest

from app.db.models import Report, Subscription
from app.ui.gradio_app import (
    _selected_delete_subscription_id,
    build_gradio_app,
    default_week_date_range,
    format_report_choices,
    format_subscription_choices,
    format_subscription_rows,
    load_reports_for_ui,
    parse_ui_date,
)


def test_build_gradio_app_contains_core_ui_labels():
    gradio = pytest.importorskip("gradio")

    ui = build_gradio_app()
    config = ui.render().get_config_file()
    labels = {
        component["props"].get("label")
        for component in config["components"]
        if isinstance(component.get("props"), dict)
    }
    style_component = next(component for component in config["components"] if component["type"] == "html")
    preview_component = next(
        component
        for component in config["components"]
        if component.get("props", {}).get("label") == "简报预览"
    )

    assert isinstance(ui, gradio.Blocks)
    assert style_component["props"]["visible"] is True
    assert preview_component["props"]["elem_id"] == "report-preview"
    assert "GitHub Sentinel Dashboard" in config["title"]
    assert "报告中心" in str(config)
    assert "report-center-shell" in str(config)
    assert "report-controls" in str(config)
    assert "report-select-row" in str(config)
    assert "report-query-button" in str(config)
    assert "report-date-inline" in str(config)
    assert "report-date-field" in str(config)
    assert "report-action-section" in str(config)
    assert "report-generate-section" in str(config)
    assert "report-preview .prose" in str(config)
    assert "report-preview .markdown" in str(config)
    assert "report-preview-column > .gap" in str(config)
    config_text = str(config)
    assert config_text.index("fitReportCalendarsToViewport();") < config_text.index(
        "localizeReportCalendars();",
    )
    assert "# border" not in config_text
    assert "border-radius: 8px" in config_text
    assert "background: #2f6b4f" in config_text
    assert "border: 1px solid #2f6b4f" in config_text
    assert "transform: translateY(-10px)" in config_text
    assert ".report-query-button:hover" in config_text
    assert "transform: none !important" in config_text
    assert "flex-wrap: nowrap !important" in config_text
    assert "flex-shrink: 0 !important" in config_text
    assert ".report-action-section > .styler" in config_text
    assert "background-color: #fbfcfa !important" in config_text
    assert "background-image: none !important" in config_text
    assert "flex-direction: column !important" in config_text
    assert "width: auto !important" in config_text
    assert "flex: 0 0 92px !important" in config_text
    assert ":has(.report-query-button)" in config_text
    assert "max-width: none !important" in config_text
    assert "max-height: min(360px" in config_text
    assert ".picker-container" in config_text
    assert "bottom: 12px !important" in config_text
    assert "top: auto !important" in config_text
    assert "calendar.style.maxHeight" in config_text
    assert 'document.querySelectorAll(".picker-container")' in config_text
    assert "root.parentElement" not in config_text
    assert "#report-preview .prose" in config_text
    assert "overflow: visible !important" in config_text
    assert "overflow: hidden" in str(config)
    assert "overflow-y: auto" in str(config)
    assert "报告查看" not in str(config)
    assert "报告列表" not in labels
    assert "开始日期" in labels
    assert "结束日期" in labels
    assert "生成开始日期" in labels
    assert "生成结束日期" in labels
    assert "简报预览" in labels
    assert "选择报告" in labels
    assert "查询" in str(config)
    assert "请选择开始日期" in str(config)
    assert "请选择结束日期" in str(config)
    assert "copy" in str(config)
    assert "REPORT_MONTHS" in str(config)
    assert "REPORT_DATE_ACTIONS" in str(config)
    assert "Clear: " in str(config)
    assert "年${REPORT_MONTHS" in str(config)
    assert "page-level" not in str(config)
    assert "按订阅间隔抓取" not in str(config)
    assert "刷新报告" not in str(config)


def test_build_gradio_app_defaults_report_dates_to_one_week_range():
    ui = build_gradio_app()
    config = ui.render().get_config_file()
    component_by_label = {
        component["props"].get("label"): component
        for component in config["components"]
        if isinstance(component.get("props"), dict)
    }
    start_date, end_date = default_week_date_range()

    assert component_by_label["报告列表范围"]["props"]["value"] == "7d"
    assert component_by_label["开始日期"]["props"]["value"] == start_date.isoformat()
    assert component_by_label["结束日期"]["props"]["value"] == end_date.isoformat()
    assert component_by_label["生成开始日期"]["props"]["value"] == start_date.isoformat()
    assert component_by_label["生成结束日期"]["props"]["value"] == end_date.isoformat()


def test_build_gradio_app_places_report_filters_under_report_selector():
    ui = build_gradio_app()
    config = ui.render().get_config_file()
    labels = {
        component["id"]: component["props"].get("label")
        for component in config["components"]
        if isinstance(component.get("props"), dict)
    }
    dependencies = [
        dependency
        for dependency in config["dependencies"]
        if str(dependency.get("api_name", "")).startswith("load_reports_for_ui")
    ]

    assert labels
    assert "报告列表范围" in labels.values()
    assert "选择报告" in labels.values()
    assert "toggle_custom_report_window" in str(config)
    assert "report-date-inline" in str(config)
    assert dependencies
    report_load_events = {
        dependency.get("targets", [[None]])[0][1]
        for dependency in dependencies
    }
    assert {"change", "click"}.issubset(report_load_events)


def test_parse_ui_date_accepts_picker_values_and_rejects_invalid_value():
    assert parse_ui_date("2026-06-01") == date(2026, 6, 1)
    assert parse_ui_date(datetime(2026, 6, 1, 9, 30)) == date(2026, 6, 1)

    with pytest.raises(ValueError, match="日期格式必须为 YYYY-MM-DD"):
        parse_ui_date("2026/06/01")


def test_format_subscription_choices_uses_repository_identity():
    subscriptions = [
        Subscription(
            id=1,
            platform="github",
            owner="acme",
            repo="sentinel",
            repository_url="https://github.com/acme/sentinel",
            interval_seconds=60,
        ),
    ]

    assert format_subscription_choices(subscriptions) == [
        ("#1 github acme/sentinel", 1),
    ]


def test_format_subscription_rows_adds_delete_action_column():
    subscriptions = [
        Subscription(
            id=1,
            platform="github",
            owner="acme",
            repo="sentinel",
            repository_url="https://github.com/acme/sentinel",
            interval_seconds=60,
            access_token_encrypted="encrypted-token",
        ),
    ]

    assert format_subscription_rows(subscriptions)[0][-1] == "删除"


def test_selected_delete_subscription_id_accepts_gradio_dataframe_value():
    pd = pytest.importorskip("pandas")

    rows = pd.DataFrame(
        [[12, "github", "acme/sentinel", 60, "已配置", "", "", "启用", "删除"]],
        columns=["ID", "平台", "仓库", "间隔秒数", "Token", "上次运行", "下次运行", "状态", "操作"],
    )
    event = type("SelectEvent", (), {"index": (0, 8)})()

    assert _selected_delete_subscription_id(rows, event) == 12


def test_selected_delete_subscription_id_ignores_non_action_column():
    rows = [[12, "github", "acme/sentinel", 60, "已配置", "", "", "启用", "删除"]]
    event = type("SelectEvent", (), {"index": (0, 2)})()

    assert _selected_delete_subscription_id(rows, event) is None


async def test_load_reports_for_ui_requires_custom_date_range():
    report_select, generated_at, preview, status = await load_reports_for_ui(1, "custom", None, None)

    assert report_select["choices"] == []
    assert generated_at == "报告生成时间：未选择报告"
    assert preview == "请选择左侧报告后查看内容。"
    assert status == "请选择报告列表范围的开始日期和结束日期。"


def test_format_report_choices_uses_report_name_and_generated_time():
    reports = [
        Report(
            id=7,
            subscription_id=1,
            name="acme_sentinel_2026-06-01",
            content_markdown="# report",
            generated_at=datetime(2026, 6, 1, 9, 30),
            period_start_date=date(2026, 6, 1),
            period_end_date=date(2026, 6, 3),
        ),
    ]

    assert format_report_choices(reports) == [
        ("sentinel（2026-06-01~2026-06-03）", 7),
    ]
