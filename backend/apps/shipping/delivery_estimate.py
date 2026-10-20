"""
shipping.delivery_estimate
~~~~~~~~~~~~~~~~~~~~~~~~~~
"Delivery by Thu, 24 Oct" for a pincode, shown on the product page before
anything is in the cart.

Where the numbers come from, in order:
  1. Shiprocket courier serviceability, when Shiprocket is the active
     provider and has a pickup pincode (also says if the pincode is served).
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
    """City/state from the India Post lookup the address form already uses."""
    try:
        from apps.address.services.address_service import AddressService

        found = AddressService().get_from_pincode(pincode) or {}
    except Exception:  # noqa: BLE001 - a missing city must never break the estimate
        return {"city": "", "state": "", "lookup_ok": False}
    return {
        "city": str(found.get("city") or ""),
        "state": str(found.get("state") or ""),
        "lookup_ok": True,
    }


def _live_days(pincode: str) -> dict[str, Any] | None:
    """Shiprocket's answer, or None when it isn't configured or didn't answer."""
    from . import services

    if services.get_active_provider_name() != "shiprocket":
        return None
    try:
        from .providers.shiprocket import ShiprocketProvider

        result = ShiprocketProvider().delivery_days_for_pincode(pincode)
    except Exception as exc:  # noqa: BLE001
        logger.warning("delivery_estimate_live_failed", pincode=pincode, error=str(exc))
        return None
    if not result.success:
        logger.info("delivery_estimate_live_unavailable", pincode=pincode, code=result.error_code)
        return None
    return result.data


def _compute(pincode: str) -> dict[str, Any]:
    cfg = _config()
    dispatch = _int(cfg.get("dispatch_days"), 1)
    place = _place(pincode)

    local = {str(p).strip() for p in (cfg.get("local_pincodes") or [])}
    if pincode in local:
        low = _int(cfg.get("local_min_days"), 0)
        high = max(low, _int(cfg.get("local_max_days"), 1))
        return {"serviceable": True, "min_days": low, "max_days": high, "source": "local",
                "city": place["city"], "state": place["state"]}

    live = _live_days(pincode)
    if live is not None:
        if not live.get("serviceable"):
            return {"serviceable": False, "min_days": None, "max_days": None, "source": "shiprocket",
                    "city": place["city"] or live.get("city", ""), "state": place["state"] or live.get("state", "")}
        if live.get("days"):
            low = int(live["days"]) + dispatch
            return {"serviceable": True, "min_days": low, "max_days": low + LIVE_ESTIMATE_SPREAD_DAYS,
                    "source": "shiprocket",
                    "city": place["city"] or live.get("city", ""), "state": place["state"] or live.get("state", "")}

    # India Post doesn't know this pincode: almost certainly a typo.
    if place["lookup_ok"] and not place["city"] and not place["state"]:
        return {"serviceable": False, "min_days": None, "max_days": None, "source": "lookup",
                "city": "", "state": "", "reason": "unknown_pincode"}

    low, high = _configured_range()
    return {"serviceable": None, "min_days": low + dispatch, "max_days": high + dispatch,
            "source": "configured", "city": place["city"], "state": place["state"]}


def estimate_delivery(pincode: str, *, today: date | None = None) -> dict[str, Any]:
    """
    Raises ValueError for a malformed pincode.

    serviceable: True / False, or None when only the configured range is known.
    """
    pincode = str(pincode or "").strip()
    if not PINCODE_RE.match(pincode):
        raise ValueError("Enter a valid 6-digit pincode.")

    key = f"shipping:delivery_estimate:v1:{pincode}"
    data = cache.get(key)
    if not isinstance(data, dict):
        data = _compute(pincode)
        cache.set(key, data, timeout=CACHE_TTL_SECONDS)

    today = today or timezone.localdate()
    result = {"pincode": pincode, **data}
    if data.get("min_days") is not None and data.get("max_days") is not None:
        result["earliest_date"] = (today + timedelta(days=int(data["min_days"]))).isoformat()
        result["latest_date"] = (today + timedelta(days=int(data["max_days"]))).isoformat()
    else:
        result["earliest_date"] = None
        result["latest_date"] = None
    return result
