"""
Structured logging configuration using structlog.

Provides both JSON (for production) and console-friendly (for development)
output, with log rotation handled by stdlib logging.
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

import structlog


def setup_logging(
    log_level: str = "DEBUG",
    log_format: str = "json",
    log_file: Path | None = None,
    log_rotation_mb: int = 50,
    log_retention_count: int = 5,
) -> None:
    """
    Configure structlog and stdlib logging for the application.

    Args:
        log_level: Root log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_format: Output format — "json" for structured or "console" for human-readable.
        log_file: Path to the log file. Creates parent directories if needed.
        log_rotation_mb: Maximum size in MB before rotating the log file.
        log_retention_count: Number of rotated log files to keep.
    """
    level = getattr(logging, log_level.upper(), logging.DEBUG)

    # ── Stdlib handler setup ─────────────────────────────────────────────
    handlers: list[logging.Handler] = []

    # Always log to stderr
    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setLevel(level)
    handlers.append(stream_handler)

    # Optionally log to a rotating file
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            filename=str(log_file),
            maxBytes=log_rotation_mb * 1024 * 1024,
            backupCount=log_retention_count,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        handlers.append(file_handler)

    # Reset root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(level)
    for handler in handlers:
        root_logger.addHandler(handler)

    # Suppress noisy third-party loggers
    for noisy_logger in ("uvicorn.access", "asyncpg", "sqlalchemy.engine"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    # ── Structlog pipeline ───────────────────────────────────────────────
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if log_format == "json":
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Apply structlog formatting to stdlib handlers
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )
    for handler in handlers:
        handler.setFormatter(formatter)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a bound structlog logger instance."""
    return structlog.get_logger(name)
