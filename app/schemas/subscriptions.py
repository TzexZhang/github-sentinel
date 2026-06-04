"""
订阅模型，负责定义订阅的请求和响应数据结构。
订阅创建只接收仓库地址、访问令牌、订阅间隔和通知通道列表；平台、owner、repo 由仓库地址解析得到。
"""
from datetime import datetime
import hashlib
import re
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, SecretStr, computed_field, model_validator

from app.services.repository_url import parse_repository_url

Platform = Literal["github", "gitee"]
NotificationChannelType = Literal["smtp", "wecom", "webhook"]

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_notification_channel_name(
    channel_type: str,
    target: str,
    name: str | None = None,
) -> str:
    """返回通知通道名称；用户未填写时按类型和目标生成稳定别名。"""
    normalized_name = name.strip() if name else ""
    if normalized_name:
        return normalized_name

    generated_name = f"{channel_type}-{target}"
    if len(generated_name) <= 100:
        return generated_name
    digest = hashlib.sha256(target.encode()).hexdigest()[:12]
    return f"{channel_type}-{digest}"


def validate_notification_channel_target(channel_type: str, target: str) -> None:
    """按通知通道类型校验目标格式。"""
    if channel_type == "smtp":
        if not EMAIL_PATTERN.fullmatch(target):
            raise ValueError("SMTP 通知目标必须是邮箱地址。")


class NotificationChannelCreate(BaseModel):
    """创建订阅时附带的通知通道配置，只保存非敏感路由信息。"""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=100)
    channel_type: NotificationChannelType
    target: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_target_and_name(self) -> "NotificationChannelCreate":
        """确保通知目标与通道类型一致，并为可选名称补默认值。"""
        validate_notification_channel_target(self.channel_type, self.target)
        self.name = normalize_notification_channel_name(self.channel_type, self.target, self.name)
        return self


class NotificationChannelRead(BaseModel):
    """订阅响应中的通知通道摘要，不包含任何敏感密钥。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    channel_type: NotificationChannelType
    target: str
    is_active: bool


class SubscriptionCreate(BaseModel):
    """创建订阅的请求结构，仓库平台和路径由 repository_url 推导。"""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    repository_url: str = Field(min_length=1, max_length=500)
    access_token: SecretStr | None = Field(default=None, min_length=1, max_length=500)
    interval_seconds: int = Field(ge=1, le=31_536_000)
    notification_channels: list[NotificationChannelCreate] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_repository_url(self) -> "SubscriptionCreate":
        """校验仓库地址必须能解析为 GitHub 或 Gitee 仓库。"""
        parse_repository_url(self.repository_url)
        return self

    @computed_field
    @property
    def platform(self) -> Platform:
        """从仓库地址中推导代码托管平台。"""
        return cast(Platform, parse_repository_url(self.repository_url).platform)

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


class SubscriptionUpdate(BaseModel):
    """更新订阅配置的请求结构，只允许修改间隔和通知通道。"""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    interval_seconds: int = Field(ge=1, le=31_536_000)
    notification_channels: list[NotificationChannelCreate] = Field(default_factory=list, max_length=20)


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
    notification_channels: list[NotificationChannelRead] = Field(default_factory=list)
    is_active: bool
    last_run_at: datetime | None
    next_run_at: datetime | None
    created_at: datetime
    updated_at: datetime
