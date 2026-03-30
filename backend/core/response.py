from typing import Any
from rest_framework import status
from rest_framework.response import Response


# ─────────────────────────────────────────────────────────────
#  Standard Envelope Shapes
#
#  SUCCESS:
#  {
#    "success": true,
#    "message": "...",
#    "data": { ... } | [ ... ] | null,
#    "meta": { "page": 1, "total": 42, ... },   # only on lists
#    "request_id": "uuid"
#  }
#
#  ERROR:
#  {
#    "success": false,
#    "message": "...",
#    "error_code": "validation_error",
#    "errors": { "field": ["msg"] },
#    "request_id": "uuid"
#  }
# ─────────────────────────────────────────────────────────────


def success_response(
    data: Any = None,
    message: str = "Request successful.",
    status_code: int = status.HTTP_200_OK,
    meta: dict | None = None,
    request_id: str | None = None,
) -> Response:
    """
    Return a standardised success envelope.

    Usage:
        return success_response(data=serializer.data, message="User created.", status_code=201)
    """
    payload: dict = {
        "success": True,
        "message": message,
        "data": data,
    }
    if meta is not None:
        payload["meta"] = meta
    if request_id is not None:
        payload["request_id"] = request_id

    return Response(payload, status=status_code)


def error_response(
    message: str = "Request failed.",
    error_code: str = "error",
    errors: dict | None = None,
    status_code: int = status.HTTP_400_BAD_REQUEST,
    request_id: str | None = None,
) -> Response:
    """
    Return a standardised error envelope.

    Usage:
        return error_response(message="Not found.", error_code="not_found", status_code=404)
    """
    payload: dict = {
        "success": False,
        "message": message,
        "error_code": error_code,
    }
    if errors:
        payload["errors"] = errors
    if request_id is not None:
        payload["request_id"] = request_id

    return Response(payload, status=status_code)


def paginated_response(
    data: Any,
    pagination_meta: dict,
    message: str = "Request successful.",
    request_id: str | None = None,
) -> Response:
    """
    Convenience wrapper around success_response for paginated list endpoints.

    pagination_meta should include at minimum:
        { "page": 1, "page_size": 20, "total_count": 100, "total_pages": 5 }
    """
    return success_response(
        data=data,
        message=message,
        meta=pagination_meta,
        request_id=request_id,
    )
