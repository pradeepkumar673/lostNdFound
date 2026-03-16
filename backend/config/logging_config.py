"""
backend/config/logging_config.py
Structured JSON logging using structlog.
In development: pretty coloured console output.
In production:  newline-delimited JSON (compatible with Datadog / Loki / CloudWatch).
"""

from __future__ import annotations

import logging
import os
import sys

import structlog


def configure_logging() -> None:
    """
    Configure root logging + structlog processors.
    Call once at app startup (before create_app).
    """
    env        = os.getenv("FLASK_ENV", "production")
    log_level  = logging.DEBUG if env == "development" else logging.INFO
    is_dev     = env == "development"

    # ── stdlib root logger ────────────────────────────────────────────────────
    logging.basicConfig(
        format  = "%(message)s",
        stream  = sys.stdout,
        level   = log_level,
    )

    # Quieten noisy third-party loggers
    for noisy in ("werkzeug", "engineio", "socketio", "pymongo", "urllib3",
                  "transformers", "PIL"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    # ── structlog processors ──────────────────────────────────────────────────
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if is_dev:
        renderer = structlog.dev.ConsoleRenderer(colors=True)
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors              = shared_processors + [renderer],
        wrapper_class           = structlog.make_filtering_bound_logger(log_level),
        context_class           = dict,
        logger_factory          = structlog.PrintLoggerFactory(),
        cache_logger_on_first_use = True,
    )
