"""
core.logging
~~~~~~~~~~~~
Structured logging helpers for Aurora Blings.

Every app module should use `get_logger(__name__)` instead of the
stdlib `logging.getLogger(...)` directly, so all log records go
through the same structlog processor chain.

Usage:
    from core.logging import get_logger

    log = get_logger(__name__)
    log.info("order_created", order_id=str(order.id), user_id=str(user.id))
    log.warning("low_stock", sku="AB-001", qty=2)
    log.error("payment_failed", error=str(e), request_id=request_id)
"""

import logging
import structlog


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Return a structlog-bound logger wired to the stdlib 'aurora_app'
    logger hierarchy defined in settings.LOGGING.

    Args:
        name: Typically `__name__` of the calling module.

    Returns:
        A structlog BoundLogger ready to use with keyword context.
    """
    stdlib_logger = logging.getLogger(name)

    return structlog.wrap_logger(
        stdlib_logger,
        processors=[
            structlog.contextvars.merge_contextvars,         # request_id etc.
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer(),                 # dev; swap for JSONRenderer in prod
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
    )


def bind_request_context(request_id: str, user_id: str | None = None) -> None:
    """
    Bind immutable context variables to every log record for the
    duration of the current async/threading context.

    Call this once per request in the tracing middleware.

    Args:
        request_id: The UUID assigned to this HTTP request.
        user_id:    Optional authenticated user UUID.
    """
    ctx: dict = {"request_id": request_id}
    if user_id:
        ctx["user_id"] = user_id
    structlog.contextvars.bind_contextvars(**ctx)


def clear_request_context() -> None:
    """
    Remove all bound context variables at the end of the request.
    Must be called in middleware `__call__` after `get_response`.
    """
    structlog.contextvars.clear_contextvars()
