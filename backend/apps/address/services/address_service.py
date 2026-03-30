from __future__ import annotations

import re
from typing import Any

import requests

from apps.features import services as feature_services
from core.exceptions import ValidationError
from core.logging import get_logger

from apps.address.utils.cache import (
    DEFAULT_TTL_SECONDS,
    cache_get,
    cache_set,
    geo_cache_key,
    pincode_cache_key,
)

logger = get_logger(__name__)


PINCODE_REGEX = re.compile(r"^\d{6}$")
INDIA_POST_PINCODE_URL = "https://api.postalpincode.in/pincode/{pincode}"
NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"


def _empty_response() -> dict[str, Any]:
    return {
        "city": "",
        "state": "",
        "area": "",
        "areas": [],
        "pincode": "",
    }


def _clean(value: Any) -> str:
    return str(value or "").strip()


class AddressService:
    def _timeout_seconds(self) -> float:
        return float(feature_services.get_setting("address.lookup.timeout_seconds", default=3) or 3)

    def _pincode_cache_ttl(self) -> int:
        value = feature_services.get_setting("address.lookup.pincode_cache_ttl_seconds", default=DEFAULT_TTL_SECONDS)
        return int(value or DEFAULT_TTL_SECONDS)

    def _geo_cache_ttl(self) -> int:
        value = feature_services.get_setting("address.lookup.geo_cache_ttl_seconds", default=DEFAULT_TTL_SECONDS)
        return int(value or DEFAULT_TTL_SECONDS)

    def _nominatim_user_agent(self) -> str:
        return str(
            feature_services.get_setting(
                "address.lookup.nominatim_user_agent",
                default="AuroraBlings/1.0 (ops@aurorablings.com)",
            )
            or "AuroraBlings/1.0 (ops@aurorablings.com)"
        )

    def get_from_pincode(self, pincode: str) -> dict[str, Any]:
        normalized = str(pincode or "").strip()
        if not PINCODE_REGEX.match(normalized):
            raise ValidationError("Pincode must be exactly 6 digits.")

        key = pincode_cache_key(normalized)
        cached = cache_get(key)
        if isinstance(cached, dict):
            return cached

        payload = self._fetch_india_post(normalized)
        cache_set(key, payload, timeout=self._pincode_cache_ttl())
        return payload

    def get_from_coordinates(self, lat: float, lng: float) -> dict[str, Any]:
        lat_value = float(lat)
        lng_value = float(lng)
        if lat_value < -90 or lat_value > 90:
            raise ValidationError("Latitude must be between -90 and 90.")
        if lng_value < -180 or lng_value > 180:
            raise ValidationError("Longitude must be between -180 and 180.")

        key = geo_cache_key(lat_value, lng_value)
        cached = cache_get(key)
        if isinstance(cached, dict):
            return cached

        payload = self._fetch_reverse(lat_value, lng_value)
        cache_set(key, payload, timeout=self._geo_cache_ttl())
        return payload

    def _fetch_india_post(self, pincode: str) -> dict[str, Any]:
        # TODO(address): Add Shiprocket serviceability check hook for checkout pre-validation.
        # TODO(address): Add internal pincode DB fallback when external providers degrade.
        # TODO(address): Add fraud heuristics for low-confidence or mismatched address patterns.
        # TODO(address): Add ranked address suggestions/autocomplete for area and landmarks.
        url = INDIA_POST_PINCODE_URL.format(pincode=pincode)
        try:
            response = requests.get(url, timeout=self._timeout_seconds())
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            logger.warning("pincode_lookup_failed", pincode=pincode, error=str(exc))
            return _empty_response()

        if not isinstance(data, list) or not data:
            return _empty_response()

        row = data[0] if isinstance(data[0], dict) else {}
        if str(row.get("Status", "")).lower() != "success":
            return _empty_response()

        post_offices = row.get("PostOffice")
        if not isinstance(post_offices, list) or not post_offices:
            return _empty_response()

        first = post_offices[0] if isinstance(post_offices[0], dict) else {}
        # Prefer "Region" for city-style values (e.g., Bhubaneswar) and
        # fall back to district/division names.
        city = _clean(first.get("Region")) or _clean(first.get("District")) or _clean(first.get("Division"))
        state = _clean(first.get("State"))

        seen: set[str] = set()
        areas: list[str] = []
        for office in post_offices:
            if not isinstance(office, dict):
                continue
            area_name = _clean(office.get("Name"))
            if not area_name:
                continue
            key = area_name.lower()
            if key in seen:
                continue
            seen.add(key)
            areas.append(area_name)

        if not city:
            for office in post_offices:
                if not isinstance(office, dict):
                    continue
                city = _clean(office.get("Region")) or _clean(office.get("District")) or _clean(office.get("Division"))
                if city:
                    break

        return {
            "city": city,
            "state": state,
            "area": areas[0] if areas else "",
            "areas": areas,
            "pincode": _clean(first.get("Pincode")) or _clean(pincode),
        }

    def _fetch_reverse(self, lat: float, lng: float) -> dict[str, Any]:
        params = {
            "lat": lat,
            "lon": lng,
            "format": "jsonv2",
            "addressdetails": 1,
        }
        headers = {
            "User-Agent": self._nominatim_user_agent(),
        }
        try:
            response = requests.get(
                NOMINATIM_REVERSE_URL,
                params=params,
                headers=headers,
                timeout=self._timeout_seconds(),
            )
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            logger.warning("reverse_lookup_failed", lat=lat, lng=lng, error=str(exc))
            return _empty_response()

        address = data.get("address") if isinstance(data, dict) else {}
        if not isinstance(address, dict):
            return _empty_response()

        city = str(
            address.get("city")
            or address.get("town")
            or address.get("village")
            or address.get("municipality")
            or address.get("county")
            or ""
        ).strip()
        state = str(address.get("state") or "").strip()
        area = str(
            address.get("suburb")
            or address.get("neighbourhood")
            or address.get("city_district")
            or address.get("road")
            or ""
        ).strip()
        areas = [area] if area else []
        raw_postcode = str(address.get("postcode") or "").strip()
        pincode = "".join(ch for ch in raw_postcode if ch.isdigit())[:6]

        return {
            "city": city,
            "state": state,
            "area": area,
            "areas": areas,
            "pincode": pincode,
        }
