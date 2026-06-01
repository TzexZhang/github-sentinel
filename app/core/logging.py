"""应用日志初始化模块。"""

import json
import logging as std_logging
import sys
from datetime import UTC, datetime
from typing import Any

LOGGER_NAME = "github_sentinel"


class JsonFormatter(std_logging.Formatter):
    """把日志记录格式化为便于检索的 JSON 行。"""

    def format(self, record: std_logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "time": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["error"] = self.formatException(record.exc_info)

        for field in (
            "request_id",
            "subscription_id",
            "owner",
            "repo",
            "duration_ms",
            "fetched_events",
            "stored_events",
            "report_id",
        ):
            if hasattr(record, field):
                payload[field] = getattr(record, field)

        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str = "INFO", log_format: str = "json") -> None:
    """配置项目日志，重复调用时会替换旧 handler，避免测试或重载时重复输出。"""
    logger = std_logging.getLogger(LOGGER_NAME)
    logger.handlers.clear()
    logger.setLevel(_resolve_level(level))
    logger.propagate = False

    handler = std_logging.StreamHandler(sys.stdout)
    handler.setLevel(_resolve_level(level))
    if log_format.strip().lower() == "text":
        handler.setFormatter(
            std_logging.Formatter(
                "%(asctime)s %(levelname)s [%(name)s] %(message)s",
            ),
        )
    else:
        handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)


def get_logger(name: str) -> std_logging.Logger:
    """返回项目命名空间下的 logger。"""
    return std_logging.getLogger(f"{LOGGER_NAME}.{name}")


def _resolve_level(level: str) -> int:
    normalized = level.strip().upper()
    return getattr(std_logging, normalized, std_logging.INFO)
