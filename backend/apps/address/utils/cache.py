from __future__ import annotations

from django.core.cache import cache


PINCODE_CACHE_PREFIX = "address:pincode"
GEO_CACHE_PREFIX = "address:geo"
DEFAULT_TTL_SECONDS = 86400


def pincode_cache_key(pincode: str) -> str:
    return f"{PINCODE_CACHE_PREFIX}:{pincode}"


def geo_cache_key(lat: float, lng: float) -> str:
    lat_key = f"{lat:.5f}"
    lng_key = f"{lng:.5f}"
    return f"{GEO_CACHE_PREFIX}:{lat_key}:{lng_key}"


def cache_get(key: str):
    return cache.get(key)


def cache_set(key: str, value, timeout: int = DEFAULT_TTL_SECONDS) -> None:
    cache.set(key, value, timeout=timeout)

