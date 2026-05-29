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

    # Path.open("rb"): 以二进制只读模式打开文件
    # 使用 "rb" 而非 "r" 是因为 tomllib.load() 要求接收二进制流（BinaryIO），
    # TOML 规范要求解析器按字节处理以正确处理编码声明
    with config_path.open("rb") as config_file:
        # tomllib.load(): Python 3.11+ 内置的 TOML 解析器，从二进制流读取并返回 dict
        return tomllib.load(config_file)


# project_config: {'app': {'name': 'GitHub Sentinel'}, 'database': {'url': 'sqlite+aiosqlite:///./github_sentinel.db'}}
project_config = load_project_config()  
app_config = project_config.get("app", {}) # dict.get(key, default)
database_config = project_config.get("database", {})


class Settings(BaseSettings):
    """应用运行配置，统一承载应用名称、数据库地址和敏感令牌配置。"""

    model_config = SettingsConfigDict(extra="ignore")

    # 非敏感默认值来自配置文件，敏感项仍由环境变量注入。
    app_name: str = str(app_config.get("name", "GitHub Sentinel"))
    database_url: str = str(
        database_config.get("url", "sqlite+aiosqlite:///./github_sentinel.db"),
    )
    github_token: str | None = Field(default=None, repr=False)
    gitee_token: str | None = Field(default=None, repr=False)
    token_encryption_key: str | None = Field(default=None, repr=False)


settings = Settings()
