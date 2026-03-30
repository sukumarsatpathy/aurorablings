"""
features.services
~~~~~~~~~~~~~~~~~

Public API:
═══════════

Feature flags:
  is_feature_enabled(code, user_id=None)  → bool
  enable_feature(code, by_user, notes)
  disable_feature(code, by_user, notes)
  set_rollout(code, percentage, by_user)
  require_feature(code, user_id=None)     → raises FeatureDisabledError

Provider config:
  get_provider_config(feature_code, provider_key)   → dict (cached)
  set_provider_config(feature_code, provider_key, config, by_user)
  activate_provider(feature_code, provider_key)
  get_active_provider_config(feature_code)          → (provider_key, dict) | None

App settings:
  get_setting(key, default=None)          → typed value (cached)
  get_settings_by_category(category)      → {key: value}
  get_public_settings()                   → {key: value} all public settings (cached batch)
  set_setting(key, value, by_user=None)
  bulk_set_settings(data, by_user=None)   → {key: value}
  ensure_setting(key, value, **defaults)  → creates only if missing

Seeding:
  seed_features(feature_list)             → upsert Feature + FeatureFlag rows
  seed_settings(settings_list)            → upsert AppSetting rows
"""

from __future__ import annotations

from decimal import Decimal
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from core.logging import get_logger

from .models import Feature, FeatureFlag, ProviderConfig, AppSetting, SettingType
from . import cache as _cache
from .media_cleanup import cleanup_replaced_media
from .security import is_secret_setting, sanitize_settings_for_response

logger = get_logger(__name__)

TURNSTILE_CONFIG_CACHE_KEY = "settings:turnstile:config"
TURNSTILE_CONFIG_TTL_SECONDS = 60


# ─────────────────────────────────────────────────────────────
#  Exceptions
# ─────────────────────────────────────────────────────────────

class FeatureDisabledError(Exception):
    """Raised when a required feature is off."""
    def __init__(self, code: str):
        super().__init__(f"Feature '{code}' is disabled.")
        self.code = code


class FeatureNotFoundError(Exception):
    def __init__(self, code: str):
        super().__init__(f"Feature '{code}' does not exist.")
        self.code = code


# ─────────────────────────────────────────────────────────────
#  1.  Feature Flags
# ─────────────────────────────────────────────────────────────

def is_feature_enabled(code: str, user_id=None) -> bool:
    """
    Check whether a feature is enabled.

    1. Hit Redis cache (feature:flag:{code}).
    2. On miss, query DB and repopulate cache.
    3. Gradual rollout: if rollout_pct < 100, hash(user_id) % 100 < pct.

    Returns False for unknown features (fail-closed).
    """
    cached = _cache.get_cached_flag(code)
    if cached is not _cache.SENTINEL:
        is_enabled, rollout_pct = cached
    else:
        try:
            flag = (
                FeatureFlag.objects
                .select_related("feature")
                .get(feature__code=code)
            )
            is_enabled  = flag.is_enabled and flag.feature.is_available
            rollout_pct = flag.rollout_percentage
        except FeatureFlag.DoesNotExist:
            logger.debug("feature_flag_not_found", code=code)
            return False

        _cache.set_cached_flag(code, is_enabled, rollout_pct)

    if not is_enabled:
        return False

    if rollout_pct >= 100:
        return True

    if rollout_pct <= 0:
        return False

    # Gradual rollout by user hash
    if user_id is None:
        return False   # non-authenticated requests get no access during rollout
    return (hash(str(user_id)) % 100) < rollout_pct


def require_feature(code: str, user_id=None) -> None:
    """Raise FeatureDisabledError if the feature is not enabled."""
    if not is_feature_enabled(code, user_id=user_id):
        raise FeatureDisabledError(code)


@transaction.atomic
def enable_feature(code: str, by_user=None, notes: str = "") -> FeatureFlag:
    """Enable a feature and record who did it."""
    feature = _get_feature_or_raise(code)
    flag, _created = FeatureFlag.objects.get_or_create(
        feature=feature,
        defaults={"is_enabled": False, "rollout_percentage": 100},
    )
    flag.is_enabled     = True
    flag.enabled_at     = timezone.now()
    flag.disabled_at    = None
    flag.enabled_by     = by_user
    flag.notes          = notes
    flag.save()
    _cache.delete_flag_cache(code)
    logger.info("feature_enabled", code=code, by=str(by_user))
    return flag


@transaction.atomic
def disable_feature(code: str, by_user=None, notes: str = "") -> FeatureFlag:
    """Disable a feature."""
    feature = _get_feature_or_raise(code)
    flag, _created = FeatureFlag.objects.get_or_create(
        feature=feature,
        defaults={"is_enabled": True, "rollout_percentage": 100},
    )
    flag.is_enabled     = False
    flag.disabled_at    = timezone.now()
    flag.notes          = notes
    flag.save()
    _cache.delete_flag_cache(code)
    logger.info("feature_disabled", code=code, by=str(by_user))
    return flag


@transaction.atomic
def set_rollout(code: str, percentage: int, by_user=None) -> FeatureFlag:
    """Set gradual rollout percentage (0–100)."""
    if not (0 <= percentage <= 100):
        raise ValueError("Rollout percentage must be between 0 and 100.")
    feature = _get_feature_or_raise(code)
    flag, _ = FeatureFlag.objects.get_or_create(feature=feature)
    flag.rollout_percentage = percentage
    flag.save(update_fields=["rollout_percentage", "updated_at"])
    _cache.delete_flag_cache(code)
    logger.info("feature_rollout_set", code=code, percentage=percentage, by=str(by_user))
    return flag


# ─────────────────────────────────────────────────────────────
#  2.  Provider Config
# ─────────────────────────────────────────────────────────────

def get_provider_config(feature_code: str, provider_key: str) -> dict:
    """
    Return provider config dict from cache or DB.
    Returns {} if not found.
    """
    cached = _cache.get_cached_provider_config(feature_code, provider_key)
    if cached is not _cache.SENTINEL:
        return cached or {}

    try:
        pc = ProviderConfig.objects.select_related("feature").get(
            feature__code=feature_code,
            provider_key=provider_key,
            is_active=True,
        )
        config = pc.config
    except ProviderConfig.DoesNotExist:
        config = {}

    _cache.set_cached_provider_config(feature_code, provider_key, config)
    return config


def get_active_provider_config(feature_code: str) -> tuple[str, dict] | None:
    """
    Return (provider_key, config) for the single active provider of a feature.
    Returns None if none is active.
    """
    try:
        pc = ProviderConfig.objects.select_related("feature").get(
            feature__code=feature_code, is_active=True
        )
        return pc.provider_key, pc.config
    except ProviderConfig.DoesNotExist:
        return None
    except ProviderConfig.MultipleObjectsReturned:
        # Degenerate state — return the most recently updated one
        pc = (
            ProviderConfig.objects
            .filter(feature__code=feature_code, is_active=True)
            .order_by("-updated_at")
            .first()
        )
        return (pc.provider_key, pc.config) if pc else None


@transaction.atomic
def set_provider_config(
    *,
    feature_code: str,
    provider_key: str,
    config: dict,
    by_user=None,
    activate: bool = True,
) -> ProviderConfig:
    """
    Create or update a ProviderConfig row.
    If activate=True, deactivates all other providers for the same feature first.
    """
    feature = _get_feature_or_raise(feature_code)

    if activate:
        ProviderConfig.objects.filter(
            feature=feature, is_active=True
        ).exclude(provider_key=provider_key).update(is_active=False)

    pc, _ = ProviderConfig.objects.get_or_create(
        feature=feature, provider_key=provider_key,
        defaults={"config": {}, "is_active": False, "created_by": by_user},
    )
    pc.config     = config
    pc.is_active  = activate
    pc.save(update_fields=["config", "is_active", "updated_at"])

    _cache.delete_provider_config_cache(feature_code, provider_key)
    logger.info("provider_config_updated", feature=feature_code, provider=provider_key)
    return pc


@transaction.atomic
def activate_provider(feature_code: str, provider_key: str) -> ProviderConfig:
    """Switch the active provider for a feature."""
    feature = _get_feature_or_raise(feature_code)
    # Deactivate all others
    ProviderConfig.objects.filter(feature=feature, is_active=True).update(is_active=False)
    try:
        pc = ProviderConfig.objects.get(feature=feature, provider_key=provider_key)
    except ProviderConfig.DoesNotExist:
        raise FeatureNotFoundError(f"{feature_code}/{provider_key}")
    pc.is_active = True
    pc.save(update_fields=["is_active", "updated_at"])
    _cache.delete_provider_config_cache(feature_code, provider_key)
    return pc


# ─────────────────────────────────────────────────────────────
#  3.  App Settings
# ─────────────────────────────────────────────────────────────

def get_setting(key: str, default=None):
    """
    Return the typed value of an AppSetting.
    Checks Redis cache first; falls back to DB.
    """
    cached = _cache.get_cached_setting(key)
    if cached is not _cache.SENTINEL:
        return cached if cached is not None else default

    try:
        setting = AppSetting.objects.get(key=key)
        value   = setting.typed_value
    except AppSetting.DoesNotExist:
        value = None

    _cache.set_cached_setting(key, value)
    return value if value is not None else default


def get_settings_by_category(category: str) -> dict:
    """Return {key: typed_value} for all settings in a category."""
    return {
        s.key: s.typed_value
        for s in AppSetting.objects.filter(category=category)
    }


def get_public_settings() -> dict:
    """
    Return all public settings as {key: typed_value}.
    Cached as a single batch for 30 minutes.
    """
    cached = _cache.get_all_public_settings()
    if cached is not None:
        return cached

    data = {
        s.key: s.typed_value
        for s in AppSetting.objects.filter(is_public=True)
        if not is_secret_setting(s.key)
    }
    _cache.set_all_public_settings(data)
    return data


def get_turnstile_config() -> dict:
    """
    Return runtime Turnstile config with priority:
      1) Admin AppSetting (DB)
      2) Environment fallback

    Result:
      {"enabled": bool, "site_key": str, "secret_key": str}
    """
    cached = cache.get(TURNSTILE_CONFIG_CACHE_KEY)
    if isinstance(cached, dict):
        return cached

    db_enabled = get_setting("turnstile_enabled", default=None)
    db_site_key = get_setting("turnstile_site_key", default=None)
    db_secret_key = get_setting("turnstile_secret_key", default=None)

    env_enabled = bool(getattr(settings, "TURNSTILE_ENABLED", False))
    env_site_key = str(getattr(settings, "TURNSTILE_SITE_KEY", "") or "").strip()
    env_secret_key = str(getattr(settings, "TURNSTILE_SECRET_KEY", "") or "").strip()

    enabled = bool(db_enabled) if db_enabled is not None else env_enabled
    site_key = str(db_site_key or "").strip() if str(db_site_key or "").strip() else env_site_key
    secret_key = str(db_secret_key or "").strip() if str(db_secret_key or "").strip() else env_secret_key

    data = {
        "enabled": enabled,
        "site_key": site_key,
        "secret_key": secret_key,
    }
    cache.set(TURNSTILE_CONFIG_CACHE_KEY, data, timeout=TURNSTILE_CONFIG_TTL_SECONDS)
    return data


@transaction.atomic
def set_setting(key: str, value, by_user=None) -> AppSetting:
    """
    Update an existing AppSetting's value.
    Value is always stored as a string; typed_value coerces on read.
    """
    try:
        setting = AppSetting.objects.select_for_update().get(key=key)
    except AppSetting.DoesNotExist:
        raise KeyError(f"Setting '{key}' does not exist. Use ensure_setting() to create.")

    if not setting.is_editable:
        from core.exceptions import ValidationError
        raise ValidationError(f"Setting '{key}' is locked and cannot be edited.")

    old_value = str(setting.value or "")
    setting.value      = _coerce_to_str(value, setting.value_type)
    setting.updated_by = by_user
    setting.save(update_fields=["value", "updated_by", "updated_at"])
    cleanup_replaced_media(old_value, setting.value)

    _cache.delete_setting_cache(key)
    logger.info("setting_updated", key=key, by=str(by_user))
    return setting


@transaction.atomic
def bulk_set_settings(data: dict, by_user=None) -> dict:
    """
    Update multiple settings at once.
    data = {key: value, ...}
    Returns {key: new_typed_value, ...}.
    """
    result = {}
    for key, value in data.items():
        s = set_setting(key, value, by_user=by_user)
        result[s.key] = s.typed_value
    return sanitize_settings_for_response(result)


def ensure_setting(key: str, value, **defaults) -> AppSetting:
    """
    Create the setting if it doesn't exist; do nothing if it does.
    Useful for migrations and initial seeding.
    """
    defaults["value"] = _coerce_to_str(value, defaults.get("value_type", SettingType.STRING))
    setting, created = AppSetting.objects.get_or_create(key=key, defaults=defaults)
    if created:
        logger.info("setting_created", key=key)
        _cache.delete_setting_cache(key)
    return setting


# ─────────────────────────────────────────────────────────────
#  4.  Seeding helpers  (used by data migrations / management commands)
# ─────────────────────────────────────────────────────────────

@transaction.atomic
def seed_features(feature_list: list[dict]) -> None:
    """
    Upsert Feature + create-only FeatureFlag rows.

    feature_list item:
      {
        "code": "payment_stripe",
        "name": "Stripe Payments",
        "category": "payment",
        "tier": "premium",
        "requires_config": True,
        "config_schema": {...},
        "is_enabled": False,  # initial flag state
      }
    """
    for data in feature_list:
        is_enabled = data.pop("is_enabled", False)
        feature, _ = Feature.objects.update_or_create(
            code=data["code"],
            defaults=data,
        )
        FeatureFlag.objects.get_or_create(
            feature=feature,
            defaults={"is_enabled": is_enabled, "rollout_percentage": 100},
        )
    logger.info("features_seeded", count=len(feature_list))


@transaction.atomic
def seed_settings(settings_list: list[dict]) -> None:
    """
    Upsert AppSetting rows.

    settings_list item:
      {
        "key": "site_name",
        "value": "Aurora Blings",
        "value_type": "string",
        "category": "branding",
        "label": "Site Name",
        "is_public": True,
      }
    """
    for data in settings_list:
        AppSetting.objects.update_or_create(key=data["key"], defaults=data)
    logger.info("settings_seeded", count=len(settings_list))


# ─────────────────────────────────────────────────────────────
#  Private helpers
# ─────────────────────────────────────────────────────────────

def _get_feature_or_raise(code: str) -> Feature:
    try:
        return Feature.objects.get(code=code)
    except Feature.DoesNotExist:
        raise FeatureNotFoundError(code)


def _coerce_to_str(value, value_type: str) -> str:
    import json
    if value_type == SettingType.BOOLEAN:
        return "true" if (value is True or str(value).lower() in ("true", "1", "yes")) else "false"
    if value_type == SettingType.JSON and isinstance(value, (dict, list)):
        return json.dumps(value)
    return str(value)
