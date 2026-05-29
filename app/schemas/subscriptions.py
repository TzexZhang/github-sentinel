"""
订阅模型，负责定义订阅的请求和响应数据结构。
订阅创建只接收仓库地址、访问令牌、订阅间隔和通知通道；平台、owner、repo 由仓库地址解析得到。
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, computed_field, model_validator

from app.services.repository_url import parse_repository_url

Platform = Literal["github", "gitee"]


class SubscriptionCreate(BaseModel):
    """创建订阅的请求结构，仓库平台和路径由 repository_url 推导。"""

    model_config = ConfigDict(str_strip_whitespace=True)

    repository_url: str = Field(min_length=1, max_length=500)
    access_token: SecretStr | None = Field(default=None, min_length=1, max_length=500)
    interval_seconds: int = Field(ge=1, le=31_536_000)
    notification_channel: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def validate_repository_url(self) -> "SubscriptionCreate":
        """校验仓库地址必须能解析为 GitHub 或 Gitee 仓库。"""
        parse_repository_url(self.repository_url)
        return self

    @computed_field
    @property
    def platform(self) -> Platform:
        """从仓库地址中推导代码托管平台。"""
        return parse_repository_url(self.repository_url).platform  # type: ignore[return-value]

    @computed_field
    @property
    def owner(self) -> str:
        """从仓库地址中推导仓库拥有者。"""
        return parse_repository_url(self.repository_url).owner

    @computed_field
    @property
    def repo(self) -> str:
        """从仓库地址中推导仓库名称。"""
        return parse_repository_url(self.repository_url).repo

    @computed_field
    @property
    def normalized_repository_url(self) -> str:
        """返回去除 .git 后缀和多余路径后的标准仓库地址。"""
        return parse_repository_url(self.repository_url).normalized_url


class SubscriptionRead(BaseModel):
    """订阅列表与创建接口的响应结构，敏感令牌仅暴露配置状态。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    platform: Platform
    owner: str
    repo: str
    repository_url: str
    interval_seconds: int
    token_configured: bool
    notification_channel: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
