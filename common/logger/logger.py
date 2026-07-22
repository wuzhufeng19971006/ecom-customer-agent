"""结构化日志（structlog），方便调试与审计。"""

import logging
import sys

import structlog


def setup_logging(level: str = "INFO") -> structlog.BoundLogger:
    """初始化全局 structlog，返回 logger。"""
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        cache_logger_on_first_use=True,
    )
    return structlog.get_logger()


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    return structlog.get_logger(name)
