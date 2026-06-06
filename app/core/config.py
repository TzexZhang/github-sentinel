"""
配置模块，负责加载和解析项目配置文件。
"""
import os
import tomllib
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_CONFIG_PATH = Path("config/settings.toml")


def load_project_config() -> dict[str, object]:
    """加载项目 TOML 配置文件；文件不存在时返回空配置。"""
    # 默认读取仓库内正式配置文件；部署时可用环境变量切换配置路径。
    config_path = Path(os.getenv("GITHUB_SENTINEL_CONFIG", DEFAULT_CONFIG_PATH))
    if not config_path.exists():
        return {}

    # 使用 Path.open("rb") 以二进制只读模式打开文件
    # 使用 "rb" 而非 "r" 是因为 tomllib.load() 要求接收二进制流（BinaryIO），
    # TOML 规范要求解析器按字节处理以正确处理编码声明
    with config_path.open("rb") as config_file:
        # 使用 Python 3.11+ 内置的 tomllib.load() 从二进制流读取并返回字典
        return tomllib.load(config_file)


# project_config 示例：{'app': {'name': 'Git Sentinel'}, 'database': {'url': 'sqlite+aiosqlite:///./github_sentinel.db'}}
project_config = load_project_config()  
app_config = project_config.get("app", {})  # 读取指定配置段，不存在时使用默认值
database_config = project_config.get("database", {})
llm_config = project_config.get("llm", {})
llm_model_config = llm_config.get("model") if isinstance(llm_config.get("model"), str) else None
llm_base_url_config = (
    llm_config.get("base_url") if isinstance(llm_config.get("base_url"), str) else None
)


class Settings(BaseSettings):
    """应用运行配置，统一承载应用名称、数据库地址和敏感令牌配置。"""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # 非敏感默认值来自配置文件，敏感项仍由环境变量注入。
    app_name: str = str(app_config.get("name", "Git Sentinel"))
    database_url: str = str(
        database_config.get("url", "sqlite+aiosqlite:///./github_sentinel.db"),
    )
    github_token: str | None = Field(default=None, repr=False)
    gitee_token: str | None = Field(default=None, repr=False)
    token_encryption_key: str | None = Field(default=None, repr=False)
    llm_provider: str = str(llm_config.get("provider", "zhipu"))
    llm_model: str | None = llm_model_config
    llm_base_url: str | None = llm_base_url_config
    llm_api_key: str | None = Field(default=None, repr=False)
    zhipu_api_key: str | None = Field(default=None, repr=False)
    gemini_api_key: str | None = Field(default=None, repr=False)
    llm_timeout_seconds: float = float(llm_config.get("timeout_seconds", 120.0))
    log_level: str = "INFO"
    log_format: str = "json"
    scheduler_enabled: bool = True
    scheduler_tick_seconds: int = Field(default=30, ge=1)
    notification_smtp_host: str | None = None
    notification_smtp_port: int = Field(default=587, ge=1, le=65_535)
    notification_smtp_username: str | None = Field(default=None, repr=False)
    notification_smtp_password: str | None = Field(default=None, repr=False)
    notification_smtp_from_email: str | None = None
    notification_smtp_use_tls: bool = True
    notification_smtp_use_ssl: bool = False
    notification_wecom_corp_id: str | None = Field(default=None, repr=False)
    notification_wecom_agent_id: str | None = Field(default=None, repr=False)
    notification_wecom_secret: str | None = Field(default=None, repr=False)
    notification_wecom_to_user: str | None = None
    notification_wecom_callback_url: str | None = None
    notification_wecom_callback_token: str | None = Field(default=None, repr=False)
    notification_wecom_callback_encoding_aes_key: str | None = Field(default=None, repr=False)
    notification_wecom_webhook_url: str | None = Field(default=None, repr=False)
    notification_wecom_webhook_key: str | None = Field(default=None, repr=False)
    notification_dingtalk_webhook_url: str | None = Field(default=None, repr=False)
    notification_dingtalk_secret: str | None = Field(default=None, repr=False)
    notification_webhook_url: str | None = Field(default=None, repr=False)
    notification_webhook_token: str | None = Field(default=None, repr=False)
    notification_timeout_seconds: float = Field(default=10.0, ge=1.0)
    notification_worker_enabled: bool = False
    notification_worker_tick_seconds: int = Field(default=30, ge=1)
    auth_cookie_name: str = "github_sentinel_session"
    auth_session_days: int = Field(default=7, ge=1)
    admin_username: str = "admin"
    admin_password: str = Field(default="admin123", repr=False)

    @property
    def resolved_llm_api_key(self) -> str | None:
        """按通用配置和服务商专用配置解析最终使用的 LLM API Key。"""
        if self.llm_api_key:
            return self.llm_api_key
        provider = self.llm_provider.strip().lower()
        if provider == "zhipu":
            return self.zhipu_api_key
        if provider == "gemini":
            return self.gemini_api_key
        return None

    @property
    def resolved_notification_wecom_webhook_url(self) -> str | None:
        """解析企业微信 Webhook URL，兼容旧钉钉变量名。"""
        return self.notification_wecom_webhook_url or self.notification_dingtalk_webhook_url


settings = Settings()
