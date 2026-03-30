"""
features.cache
~~~~~~~~~~~~~~
Centralised cache key constants and TTLs.

All cache interaction goes through this module so keys and TTLs
are defined in one place and can be tuned without grep-hunting.
"""
from django.core.cache import cache
import json

# ── TTLs ─────────────────────────────────────────────────────
FEATURE_FLAG_TTL       = 60 * 5      # 5 minutes
PROVIDER_CONFIG_TTL    = 60 * 10     # 10 minutes
SETTING_TTL            = 60 * 15     # 15 minutes
ALL_PUBLIC_SETTINGS_TTL= 60 * 30    # 30 minutes

SENTINEL = object()   # distinguishes "not cached" from "cached as None"


# ── Key builders ─────────────────────────────────────────────

def _flag_key(code: str)                          -> str: return f"feature:flag:{code}"
def _provider_key(feature_code: str, pkey: str)   -> str: return f"feature:provider:{feature_code}:{pkey}"
def _setting_key(key: str)                         -> str: return f"setting:{key}"
ALL_PUBLIC_KEY = "settings:all_public"


# ── Feature flag ─────────────────────────────────────────────

def get_cached_flag(code: str):
    """Return (is_enabled, rollout_pct) tuple or SENTINEL if miss."""
    raw = cache.get(_flag_key(code))
    if raw is None:
        return SENTINEL
    return raw   # stored as [bool, int]


def set_cached_flag(code: str, is_enabled: bool, rollout_pct: int) -> None:
    cache.set(_flag_key(code), [is_enabled, rollout_pct], timeout=FEATURE_FLAG_TTL)


def delete_flag_cache(code: str) -> None:
    cache.delete(_flag_key(code))


# ── Provider config ──────────────────────────────────────────

def get_cached_provider_config(feature_code: str, provider_key: str) -> dict | None:
    raw = cache.get(_provider_key(feature_code, provider_key))
    if raw is None:
        return SENTINEL
    return raw


def set_cached_provider_config(feature_code: str, provider_key: str, config: dict) -> None:
    cache.set(_provider_key(feature_code, provider_key), config, timeout=PROVIDER_CONFIG_TTL)


def delete_provider_config_cache(feature_code: str, provider_key: str) -> None:
    cache.delete(_provider_key(feature_code, provider_key))


# ── App setting ───────────────────────────────────────────────

def get_cached_setting(key: str):
    raw = cache.get(_setting_key(key))
    if raw is None:
        return SENTINEL
    return raw


def set_cached_setting(key: str, value) -> None:
    cache.set(_setting_key(key), value, timeout=SETTING_TTL)


def delete_setting_cache(key: str) -> None:
    cache.delete(_setting_key(key))
    cache.delete(ALL_PUBLIC_KEY)


def get_all_public_settings() -> dict | None:
    return cache.get(ALL_PUBLIC_KEY)


def set_all_public_settings(data: dict) -> None:
    cache.set(ALL_PUBLIC_KEY, data, timeout=ALL_PUBLIC_SETTINGS_TTL)
