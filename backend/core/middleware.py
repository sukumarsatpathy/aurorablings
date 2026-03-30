import time
import uuid
from core.logging import bind_request_context, clear_request_context, get_logger

logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────
#  Request Tracing Middleware
# ─────────────────────────────────────────────────────────────

class RequestTracingMiddleware:
    """
    Attaches a unique `request_id` to every inbound HTTP request.

    The ID is:
    - Propagated from the `X-Request-ID` header if supplied by the client / proxy.
    - Generated fresh (UUID4) otherwise.

    The value is:
    - Stored on `request.request_id` for view/middleware access.
    - Bound to the structlog context so it appears in every log line.
    - Returned in the `X-Request-ID` response header.
    """

    HEADER_NAME = "X-Request-ID"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Honour upstream ID or mint a new one
        request_id = (
            request.headers.get(self.HEADER_NAME)
            or str(uuid.uuid4())
        )
        request.request_id = request_id

        # Bind to structlog context (cleared at request end)
        user_id = str(request.user.id) if hasattr(request, "user") and request.user.is_authenticated else None
        bind_request_context(request_id=request_id, user_id=user_id)

        response = self.get_response(request)

        # Echo the ID in the response so clients can correlate
        response[self.HEADER_NAME] = request_id
        clear_request_context()
        return response


# ─────────────────────────────────────────────────────────────
#  Logging Middleware
# ─────────────────────────────────────────────────────────────

class LoggingMiddleware:
    """
    Logs every request/response pair with method, path, status, and duration.
    Relies on `request.request_id` set by RequestTracingMiddleware.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.monotonic()
        logger.info(
            "request_started",
            method=request.method,
            path=request.path,
            query=request.META.get("QUERY_STRING", ""),
        )

        response = self.get_response(request)

        duration_ms = round((time.monotonic() - start) * 1000, 2)
        level = "warning" if response.status_code >= 400 else "info"
        getattr(logger, level)(
            "request_finished",
            method=request.method,
            path=request.path,
            status=response.status_code,
            duration_ms=duration_ms,
        )
        return response


# ─────────────────────────────────────────────────────────────
#  Error Handling Middleware
# ─────────────────────────────────────────────────────────────

class ErrorHandlingMiddleware:
    """
    Last-resort safety net for any uncaught exception that bypasses DRF.
    The DRF global_exception_handler covers most cases; this handles
    non-DRF code paths (e.g. middleware itself).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        except Exception as exc:                    # noqa: BLE001
            import traceback
            from django.http import JsonResponse

            request_id = getattr(request, "request_id", "N/A")
            logger.exception(
                "unhandled_exception",
                exc=str(exc),
                traceback=traceback.format_exc(),
            )
            return JsonResponse(
                {
                    "success": False,
                    "message": "An unexpected server error occurred.",
                    "error_code": "server_error",
                    "request_id": request_id,
                },
                status=500,
            )
