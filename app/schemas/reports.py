"""
报告模型，负责定义报告的请求和响应数据结构。
定义报告响应模型 `ReportRead`，用于序列化报告列表接口返回值
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ReportRead(BaseModel):
    """报告列表接口的响应数据结构。"""

    # from_attributes 允许直接从 SQLAlchemy ORM 对象序列化响应。
    model_config = ConfigDict(from_attributes=True)

    id: int
    subscription_id: int
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    generated_at: datetime
