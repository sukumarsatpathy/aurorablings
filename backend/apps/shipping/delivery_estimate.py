"""
shipping.delivery_estimate
~~~~~~~~~~~~~~~~~~~~~~~~~~
"Delivery by Thu, 24 Oct" for a pincode, shown on the product page before
anything is in the cart.

Where the numbers come from, in order:
  1. The courier service's live check — NimbusPost (when its login is
     configured) or Shiprocket — from our pickup pincode to this one. It says
     whether the pincode is served; transit days are used when it returns them.
  2. `local_pincodes` in the `shipping.delivery_estimate` setting — e.g. the
     shop's own town, delivered by hand.
  3. The configured range: `shipping.delivery_estimate` min/max days, else the
     first active shipping rule's estimated days, else 4–7.

Every estimate adds `dispatch_days` (packing time). Results are cached per
pincode; dates are recomputed on each call so a cached answer never goes stale
across midnight.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

from django.core.cache import cache
from django.utils import timezone

from apps.features import services as feature_services
from core.logging import get_logger

logger = get_logger(__name__)

PINCODE_RE = re.compile(r"^[1-9]\d{5}$")
CACHE_TTL_SECONDS = 6 * 3600
FAILED_LOOKUP_CACHE_SECONDS = 120
DEFAULT_MIN_DAYS = 4
DEFAULT_MAX_DAYS = 7
LIVE_ESTIMATE_SPREAD_DAYS = 2   # couriers quote one number; show a short range


def _config() -> dict[str, Any]:
    cfg = feature_services.get_setting("shipping.delivery_estimate", default={}) or {}
    return cfg if isinstance(cfg, dict) else {}


def _int(value: Any, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return number if number >= 0 else default


def _configured_range() -> tuple[int, int]:
    cfg = _config()
    if cfg.get("min_days") is not None and cfg.get("max_days") is not None:
        low = _int(cfg.get("min_days"), DEFAULT_MIN_DAYS)
        return low, max(low, _int(cfg.get("max_days"), DEFAULT_MAX_DAYS))

    from apps.surcharge.models import ShippingRule

    rule = ShippingRule.objects.filter(is_active=True, is_additive=False).order_by("priority").first()
    if rule:
        return rule.estimated_days_min, max(rule.estimated_days_min, rule.estimated_days_max)
    return DEFAULT_MIN_DAYS, DEFAULT_MAX_DAYS


def _place(pincode: str) -> dict[str, str]:
    """
    City/state from the India Post lookup the address form already uses.
    status: "ok" / "not_found" / "error" — only "not_found" means a bad pincode.
    """
    try:
        from apps.address.services.address_service import AddressService

        found, status = AddressService().lookup_pincode(pincode)
    except Exception:  # noqa: BLE001 - a missing city must never break the estimate
        return {"city": "", "state": "", "status": "error"}
    return {
        "city": str((found or {}).get("city") or ""),
        "state": str((found or {}).get("state") or ""),
        "status": status,
    }


def _estimate_provider() -> str:
    """
    Which courier service answers "can you deliver here, and how fast?":
    `provider` in the shipping.delivery_estimate setting if set, else NimbusPost
    when its login is configured, else Shiprocket when it's the active provider.
    """
    from . import services
    from .providers.nimbuspost import NimbusPostProvider

    chosen = str(_config().get("provider") or "").strip().lower()
    if chosen in {"nimbuspost", "shiprocket", "none"}:
        return "" if chosen == "none" else chosen
    if NimbusPostProvider().is_configured():
        return "nimbuspost"
    if services.get_active_provider_name() == "shiprocket":
        return "shiprocket"
    return ""


def _live_days(pincode: str) -> dict[str, Any] | None:
    """
    The courier service's answer — {"serviceable", "days", "city", "state", "source"} —
    or None when no service is configured or it didn't answer.
    """
    provider = _estimate_provider()
    if not provider:
        return None
    try:
        if provider == "nimbuspost":
            from .providers.nimbuspost import NimbusPostProvider

            result = NimbusPostProvider().check_serviceability(destination=pincode, timeout=8)
        else:
            from .providers.shiprocket import ShiprocketProvider

            result = ShiprocketProvider().delivery_days_for_pincode(pincode)
    except Exception as exc:  # noqa: BLE001
        logger.warning("delivery_estimate_live_failed", provider=provider, pincode=pincode, error=str(exc))
        return None
    if not result.success:
        logger.info("delivery_estimate_live_unavailable", provider=provider, pincode=pincode, code=result.error_code)
        return None
    data = result.data or {}
    return {
        "serviceable": bool(data.get("serviceable")),
        "days": data.get("days"),
        "city": str(data.get("city") or ""),
        "state": str(data.get("state") or ""),
        "source": provider,
    }


def _compute(pincode: str) -> dict[str, Any]:
    cfg = _config()
    dispatch = _int(cfg.get("dispatch_days"), 1)
    place = _place(pincode)
    city = lambda live: place["city"] or (live or {}).get("city", "")  # noqa: E731
    state = lambda live: place["state"] or (live or {}).get("state", "")  # noqa: E731

    local = {str(p).strip() for p in (cfg.get("local_pincodes") or [])}
    if pincode in local:
        low = _int(cfg.get("local_min_days"), 0)
        high = max(low, _int(cfg.get("local_max_days"), 1))
        return {"serviceable": True, "min_days": low, "max_days": high, "source": "local",
                "city": place["city"], "state": place["state"]}

    live = _live_days(pincode)
    if live is not None:
        if not live["serviceable"]:
            return {"serviceable": False, "min_days": None, "max_days": None, "source": live["source"],
                    "city": city(live), "state": state(live)}
        if live.get("days"):
            low = int(live["days"]) + dispatch
            return {"serviceable": True, "min_days": low, "max_days": low + LIVE_ESTIMATE_SPREAD_DAYS,
                    "source": live["source"], "city": city(live), "state": state(live)}
        # The courier service confirms delivery but gives no transit time
        # (NimbusPost's documented API doesn't): its yes/no plus our range.
        low, high = _configured_range()
        return {"serviceable": True, "min_days": low + dispatch, "max_days": high + dispatch,
                "source": live["source"], "city": city(live), "state": state(live)}

    # India Post answered and doesn't know this pincode: almost certainly a typo.
    # (If India Post just didn't answer, fall through to the normal estimate.)
    if place["status"] == "not_found":
        return {"serviceable": False, "min_days": None, "max_days": None, "source": "lookup",
                "city": "", "state": "", "reason": "unknown_pincode"}

    low, high = _configured_range()
    return {"serviceable": None, "min_days": low + dispatch, "max_days": high + dispatch,
            "source": "configured", "city": place["city"], "state": place["state"],
            # Retry soon if India Post or a configured courier service didn't answer.
            "lookup_failed": place["status"] == "error" or bool(_estimate_provider())}


def estimate_delivery(pincode: str, *, today: date | None = None) -> dict[str, Any]:
    """
    Raises ValueError for a malformed pincode.

    serviceable: True / False, or None when only the configured range is known.
    """
    pincode = str(pincode or "").strip()
    if not PINCODE_RE.match(pincode):
        raise ValueError("Enter a valid 6-digit pincode.")

    key = f"shipping:delivery_estimate:v2:{pincode}"
    data = cache.get(key)
    if not isinstance(data, dict):
        data = _compute(pincode)
        # A lookup that failed is retried soon instead of being remembered for hours.
        ttl = FAILED_LOOKUP_CACHE_SECONDS if data.pop("lookup_failed", False) else CACHE_TTL_SECONDS
        cache.set(key, data, timeout=ttl)

    today = today or timezone.localdate()
    result = {"pincode": pincode, **data}
    if data.get("min_days") is not None and data.get("max_days") is not None:
        result["earliest_date"] = (today + timedelta(days=int(data["min_days"]))).isoformat()
        result["latest_date"] = (today + timedelta(days=int(data["max_days"]))).isoformat()
    else:
        result["earliest_date"] = None
        result["latest_date"] = None
    return result
