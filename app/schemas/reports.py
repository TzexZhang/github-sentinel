"""报告请求与响应结构。"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

from app.services.time_utils import format_report_datetime


class ReportGenerateRequest(BaseModel):
    """根据用户选择的日期范围生成报告的请求体。"""

    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_date_range(self) -> "ReportGenerateRequest":
        """确保选择的日期范围顺序正确。"""
        if self.end_date < self.start_date:
            raise ValueError("end_date 必须大于或等于 start_date")
        return self


class ReportListItem(BaseModel):
    """浏览订阅报告时使用的精简报告项。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    subscription_id: int
    name: str = Field(min_length=1)
    generated_at: datetime
    period_start_date: date | None = None
    period_end_date: date | None = None

    @field_serializer("generated_at")
    def serialize_generated_at(self, value: datetime) -> str:
        """把报告生成时间统一输出为本地时间字符串。"""
        return format_report_datetime(value)


class ReportRead(ReportListItem):
    """完整报告响应，包含 Markdown 正文。"""

    content_markdown: str = Field(min_length=1)
