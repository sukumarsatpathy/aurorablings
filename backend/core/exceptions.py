import logging
from django.core.exceptions import PermissionDenied, ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_default_handler

from .response import error_response

logger = logging.getLogger("aurora_app")


# ─────────────────────────────────────────────────────────────
#  Custom Exception Types
# ─────────────────────────────────────────────────────────────

class AuroraBaseException(Exception):
    """Base exception for all Aurora Blings domain errors."""
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_message = "An unexpected error occurred."
    default_code = "server_error"

    def __init__(self, message=None, code=None, extra=None):
        self.message = message or self.default_message
        self.code = code or self.default_code
        self.extra = extra or {}
        super().__init__(self.message)


class ValidationError(AuroraBaseException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_message = "Validation failed."
    default_code = "validation_error"


class NotFoundError(AuroraBaseException):
    status_code = status.HTTP_404_NOT_FOUND
    default_message = "Resource not found."
    default_code = "not_found"


class PermissionDeniedError(AuroraBaseException):
    status_code = status.HTTP_403_FORBIDDEN
    default_message = "You do not have permission to perform this action."
    default_code = "permission_denied"


class ConflictError(AuroraBaseException):
    status_code = status.HTTP_409_CONFLICT
    default_message = "A conflict occurred with the current state of the resource."
    default_code = "conflict"


class ServiceUnavailableError(AuroraBaseException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_message = "Service temporarily unavailable."
    default_code = "service_unavailable"


# ─────────────────────────────────────────────────────────────
#  Global Exception Handler (DRF hook)
# ─────────────────────────────────────────────────────────────

def global_exception_handler(exc, context):
    """
    Custom DRF exception handler.

    Wire up in settings:
        REST_FRAMEWORK = {
            'EXCEPTION_HANDLER': 'core.exceptions.global_exception_handler',
        }

    Normalises ALL exceptions into the standard Aurora API response shape:
        {
            "success": false,
            "message": "...",
            "error_code": "...",
            "errors": { ... },
            "request_id": "..."
        }
    """
    request = context.get("request")
    request_id = getattr(request, "request_id", "N/A") if request else "N/A"

    # ── 1. Our own domain exceptions ──────────────────────────
    if isinstance(exc, AuroraBaseException):
        logger.warning(
            f"[{request_id}] Domain error: {exc.code} — {exc.message}",
            extra={"extra": exc.extra},
        )
        return error_response(
            message=exc.message,
            error_code=exc.code,
            errors=exc.extra,
            status_code=exc.status_code,
            request_id=request_id,
        )

    # ── 2. Django core exceptions → DRF equivalents ──────────
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, PermissionDenied):
        exc = exceptions.PermissionDenied()
    elif isinstance(exc, DjangoValidationError):
        exc = exceptions.ValidationError(detail=exc.message_dict if hasattr(exc, "message_dict") else exc.messages)

    # ── 3. DRF native exceptions ──────────────────────────────
    response = drf_default_handler(exc, context)
    if response is not None:
        if isinstance(exc, exceptions.Throttled):
            logger.warning(
                f"[{request_id}] Rate limit blocked: {exc}",
                extra={
                    "wait_seconds": getattr(exc, "wait", None),
                    "path": getattr(request, "path", "") if request else "",
                    "method": getattr(request, "method", "") if request else "",
                    "remote_addr": request.META.get("REMOTE_ADDR") if request else "",
                },
            )
        logger.warning(f"[{request_id}] DRF error {response.status_code}: {exc}")
        errors = response.data if isinstance(response.data, dict) else {"detail": response.data}
        message = _extract_message(errors)
        return error_response(
            message=message,
            error_code=getattr(exc, "default_code", "api_error"),
            errors=errors,
            status_code=response.status_code,
            request_id=request_id,
        )

    # ── 4. Unhandled exceptions (500) ─────────────────────────
    logger.exception(f"[{request_id}] Unhandled exception: {exc}")
    return error_response(
        message="An unexpected server error occurred.",
        error_code="server_error",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        request_id=request_id,
    )


def _extract_message(errors: dict) -> str:
    """Pull a human-readable top-level message from a DRF error dict."""
    if "detail" in errors:
        return str(errors["detail"])
    if "non_field_errors" in errors:
        msgs = errors["non_field_errors"]
        return str(msgs[0]) if msgs else "Validation error."
    first_value = next(iter(errors.values()), None)
    if isinstance(first_value, list) and first_value:
        return str(first_value[0])
    return "Request failed."
