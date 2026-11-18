"""structlog JSON logging with a correlation run_id (NFR-04)."""

from __future__ import annotations

import logging
import uuid

import structlog
from structlog.contextvars import bind_contextvars, merge_contextvars


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(format="%(message)s", level=level)
    structlog.configure(
        processors=[
            merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level)),
        cache_logger_on_first_use=True,
    )


def new_run_id() -> str:
    run_id = uuid.uuid4().hex[:12]
    bind_contextvars(run_id=run_id)
    return run_id


def current_run_id() -> str:
    run_id = structlog.contextvars.get_contextvars().get("run_id")
    return str(run_id) if run_id else new_run_id()


log = structlog.get_logger("hotelpilot")
