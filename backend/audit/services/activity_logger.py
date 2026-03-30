from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from django.contrib.auth import get_user_model
from django.http import HttpRequest
from django.utils import timezone

from audit.models import ActivityLog, ActorType, AuditAction
from audit.request_context import get_current_request
from core.logging import get_logger

logger = get_logger(__name__)
User = get_user_model()

SENSITIVE_KEYS = {
    "password",
    "secret_key",
    "api_key",
    "webhook_secret",
    "token",
    "access_token",
    "refresh_token",
}
MASK = "********"


def sanitize_metadata(value: Any) -> Any:
    """Recursively sanitize and JSON-normalize metadata payloads."""
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            if str(key).lower() in SENSITIVE_KEYS:
                sanitized[str(key)] = MASK
            else:
                sanitized[str(key)] = sanitize_metadata(item)
        return sanitized

    if isinstance(value, list):
        return [sanitize_metadata(item) for item in value]

    if isinstance(value, tuple):
        return [sanitize_metadata(item) for item in value]

    if isinstance(value, set):
        return [sanitize_metadata(item) for item in sorted(value, key=str)]

    if isinstance(value, Decimal):
        return str(value)

    if isinstance(value, (datetime, date)):
        if isinstance(value, datetime) and timezone.is_naive(value):
            value = timezone.make_aware(value, timezone.get_current_timezone())
        return value.isoformat()

    if isinstance(value, uuid.UUID):
        return str(value)

    if hasattr(value, "pk"):
        return str(getattr(value, "pk", ""))

    if isinstance(value, (str, int, float, bool)) or value is None:
        return value

    return str(value)


def get_request_meta(request: HttpRequest | None = None) -> dict[str, str | None]:
    request = request or get_current_request()
    if not request:
        return {
            "ip_address": None,
            "user_agent": None,
            "request_id": None,
            "path": None,
            "method": None,
        }

    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    ip_address = x_forwarded_for.split(",")[0].strip() if x_forwarded_for else request.META.get("REMOTE_ADDR")

    return {
        "ip_address": ip_address,
        "user_agent": request.META.get("HTTP_USER_AGENT", "")[:2000] or None,
        "request_id": getattr(request, "request_id", None) or request.headers.get("X-Request-ID"),
        "path": request.path[:500] if getattr(request, "path", None) else None,
        "method": request.method[:16] if getattr(request, "method", None) else None,
    }


def _resolve_actor_type(user) -> str:
    if not user or not getattr(user, "is_authenticated", False):
        return ActorType.SYSTEM

    role = getattr(user, "role", "")
    if role == "admin":
        return ActorType.ADMIN
    if role == "staff":
        return ActorType.STAFF
    if role == "customer":
        return ActorType.CUSTOMER
    return ActorType.UNKNOWN


def log_activity(
    *,
    user=None,
    actor_type: str | None = None,
    action: str,
    entity_type: str,
    description: str,
    entity_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    request: HttpRequest | None = None,
) -> ActivityLog | None:
    """Persist a business-level audit event. Fails closed without breaking caller flow."""
    try:
        request_meta = get_request_meta(request)
        payload = sanitize_metadata(metadata or {})

        if action not in AuditAction.values:
            logger.warning("audit_invalid_action", action=action, entity_type=entity_type)
            return None

        return ActivityLog.objects.create(
            user=user if getattr(user, "is_authenticated", False) else None,
            actor_type=actor_type or _resolve_actor_type(user),
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id else None,
            description=description,
            metadata=payload,
            ip_address=request_meta["ip_address"],
            user_agent=request_meta["user_agent"],
            request_id=request_meta["request_id"],
            path=request_meta["path"],
            method=request_meta["method"],
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("activity_log_failed", error=str(exc), entity_type=entity_type, action=action)
        return None
