from __future__ import annotations

import secrets
from typing import Any

from django.http import HttpRequest

from .models import ConsentSource, ConsentStatus, CookieConsentLog


def get_client_ip(request: HttpRequest) -> str | None:
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip() or None
    remote_addr = request.META.get("REMOTE_ADDR", "")
    return remote_addr or None


def generate_anonymous_id() -> str:
    return f"anon_{secrets.token_urlsafe(18)}"


def _get_actor_filters(*, request: HttpRequest, anonymous_id: str | None) -> dict[str, Any]:
    if request.user and request.user.is_authenticated:
        return {"user": request.user}
    return {"anonymous_id": anonymous_id or ""}


def save_consent(data: dict[str, Any], request: HttpRequest) -> CookieConsentLog:
    anonymous_id = (data.get("anonymous_id") or "").strip() or generate_anonymous_id()
    session_id = (data.get("session_id") or "").strip() or (request.session.session_key or "")
    if not request.session.session_key:
        request.session.create()
        session_id = request.session.session_key or session_id

    categories = data["categories"]

    return CookieConsentLog.objects.create(
        user=request.user if request.user and request.user.is_authenticated else None,
        anonymous_id=anonymous_id,
        session_id=session_id,
        ip_address=get_client_ip(request),
        user_agent=(request.META.get("HTTP_USER_AGENT", "") or "")[:1024],
        consent_status=data["status"],
        consent_version=data.get("version", "1.0"),
        category_necessary=True,
        category_analytics=bool(categories.get("analytics", False)),
        category_marketing=bool(categories.get("marketing", False)),
        category_preferences=bool(categories.get("preferences", False)),
        source=data.get("source", ConsentSource.BANNER),
    )


def withdraw_consent(request: HttpRequest, anonymous_id: str | None = None) -> CookieConsentLog:
    filters = _get_actor_filters(request=request, anonymous_id=anonymous_id)

    latest = CookieConsentLog.objects.filter(**filters).order_by("-created_at").first()
    version = latest.consent_version if latest else "1.0"

    if latest:
        latest.consent_status = ConsentStatus.REJECTED_ALL
        latest.category_necessary = True
        latest.category_analytics = False
        latest.category_marketing = False
        latest.category_preferences = False
        latest.source = ConsentSource.SETTINGS_MODAL
        latest.save(
            update_fields=[
                "consent_status",
                "category_necessary",
                "category_analytics",
                "category_marketing",
                "category_preferences",
                "source",
            ]
        )

    payload = {
        "anonymous_id": anonymous_id or (latest.anonymous_id if latest else ""),
        "session_id": latest.session_id if latest else "",
        "status": ConsentStatus.REJECTED_ALL,
        "version": version,
        "source": ConsentSource.SETTINGS_MODAL,
        "categories": {
            "necessary": True,
            "analytics": False,
            "marketing": False,
            "preferences": False,
        },
    }
    return save_consent(payload, request)


def get_current_consent(*, request: HttpRequest, anonymous_id: str | None = None) -> CookieConsentLog | None:
    filters = _get_actor_filters(request=request, anonymous_id=anonymous_id)
    return CookieConsentLog.objects.filter(**filters).order_by("-created_at").first()


def get_analytics_consent_rate() -> float:
    total = CookieConsentLog.objects.count()
    if total == 0:
        return 0.0

    accepted = CookieConsentLog.objects.filter(category_analytics=True).count()
    return round((accepted / total) * 100, 2)
