"""报告链路使用的时间工具。"""

from datetime import UTC, date, datetime, time, timedelta, timezone, tzinfo

REPORT_TIMEZONE = timezone(timedelta(hours=8), "Asia/Shanghai")
REPORT_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def report_now() -> datetime:
    """返回报告生成使用的本地时区时间。"""
    return datetime.now(REPORT_TIMEZONE)


def format_report_datetime(value: datetime, naive_timezone: tzinfo = REPORT_TIMEZONE) -> str:
    """把时间格式化为报告展示格式，带时区的时间会先转换为本地时区。"""
    normalized = value
    if normalized.tzinfo is None:
        normalized = normalized.replace(tzinfo=naive_timezone)
    return normalized.astimezone(REPORT_TIMEZONE).strftime(REPORT_DATETIME_FORMAT)


def local_date_range_to_utc_bounds(start_date: date, end_date: date) -> tuple[datetime, datetime]:
    """把用户选择的本地日期范围转换为 UTC 半开时间区间。"""
    local_since = datetime.combine(start_date, time.min, tzinfo=REPORT_TIMEZONE)
    local_before = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=REPORT_TIMEZONE)
    return local_since.astimezone(UTC), local_before.astimezone(UTC)


def normalize_event_datetime(value: datetime) -> datetime:
    """把事件时间统一为 UTC 时间，便于去重、比较和入库。"""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
