import logging

from app.core.logging import configure_logging


def test_configure_logging_replaces_existing_github_sentinel_handlers():
    root_logger = logging.getLogger("github_sentinel")
    root_logger.handlers.clear()

    configure_logging(level="INFO", log_format="json")
    configure_logging(level="DEBUG", log_format="text")

    assert root_logger.level == logging.DEBUG
    assert len(root_logger.handlers) == 1
    assert root_logger.handlers[0].formatter is not None
