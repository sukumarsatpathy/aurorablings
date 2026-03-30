"""
features.models
~~~~~~~~~~~~~~~

Four model groups:

1. Feature          – catalogue of every available feature (code-slug, tier, schema)
2. FeatureFlag      – live on/off switch per feature (with rollout %)
3. ProviderConfig   – encrypted/masked credentials for a feature's backend provider
4. AppSetting       – general key-value store for site-wide config (e.g. brand name,
                       currency, tax rate, maximum cart size)

Caching:
  All read-hot data is cached via cache.py helpers.
  Every model signals invalidate their relevant cache keys on save/delete.

Design notes:
  • Feature is read-mostly and seeded via migrations/fixtures.
  • FeatureFlag is the runtime gate — the only table that changes frequently.
  • ProviderConfig stores arbitrary JSON; in production you should layer
    field-level encryption (e.g. django-encrypted-model-fields) via a
    custom `EncryptedJSONField` on top of the plain JSONField shown here.
  • AppSetting mirrors the classic wp_options / rails settings pattern
    but typed and cached.
"""

import uuid
from django.db import models
from django.core.cache import cache
from django.utils.translation import gettext_lazy as _


# ─────────────────────────────────────────────────────────────
#  Feature tier / category
# ─────────────────────────────────────────────────────────────

class FeatureTier(models.TextChoices):
    FREE        = "free",        _("Free")
    BASIC       = "basic",       _("Basic")
    PREMIUM     = "premium",     _("Premium")
    ENTERPRISE  = "enterprise",  _("Enterprise")


class FeatureCategory(models.TextChoices):
    PAYMENT      = "payment",      _("Payment")
    NOTIFICATION = "notification", _("Notification")
    SHIPPING     = "shipping",     _("Shipping")
    CATALOG      = "catalog",      _("Catalog")
    ORDER        = "order",        _("Order")
    ANALYTICS    = "analytics",    _("Analytics")
    MARKETING    = "marketing",    _("Marketing")
    SECURITY     = "security",     _("Security")
    GENERAL      = "general",      _("General")


class SettingCategory(models.TextChoices):
    GENERAL      = "general",      _("General")
    BRANDING     = "branding",     _("Branding")
    PAYMENT      = "payment",      _("Payment")
    NOTIFICATION = "notification", _("Notification")
    SHIPPING     = "shipping",     _("Shipping")
    INVENTORY    = "inventory",    _("Inventory")
    RETURNS      = "returns",      _("Returns")
    SEO          = "seo",          _("SEO")
    ADVANCED     = "advanced",     _("Advanced")


class SettingType(models.TextChoices):
    STRING  = "string",  _("String")
    INTEGER = "integer", _("Integer")
    FLOAT   = "float",   _("Float")
    BOOLEAN = "boolean", _("Boolean")
    JSON    = "json",    _("JSON")
    TEXT    = "text",    _("Text (multiline)")


# ─────────────────────────────────────────────────────────────
#  1.  Feature  — catalogue entry
# ─────────────────────────────────────────────────────────────

class Feature(models.Model):
    """
    Immutable (or slow-changing) catalogue of every feature the platform
    supports. Created once via fixture or migration, updated rarely.

    config_schema (JSON):
      Describes the keys that ProviderConfig must supply.
      Example for "payment_stripe":
        {
          "STRIPE_SECRET_KEY":       {"type": "string",  "required": true,  "secret": true},
          "STRIPE_WEBHOOK_SECRET":   {"type": "string",  "required": true,  "secret": true},
          "STRIPE_PUBLISHABLE_KEY":  {"type": "string",  "required": false, "secret": false}
        }
    """
    id             = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code           = models.SlugField(max_length=80, unique=True, db_index=True,
                                      help_text="Unique machine slug, e.g. 'payment_stripe'.")
    name           = models.CharField(max_length=200)
    description    = models.TextField(blank=True)
    category       = models.CharField(max_length=20, choices=FeatureCategory.choices,
                                      default=FeatureCategory.GENERAL)
    tier           = models.CharField(max_length=15, choices=FeatureTier.choices,
                                      default=FeatureTier.FREE)
    requires_config = models.BooleanField(
        default=False,
        help_text="If True, this feature needs an active ProviderConfig to function.",
    )
    config_schema  = models.JSONField(
        default=dict, blank=True,
        help_text="JSON schema describing required ProviderConfig keys.",
    )
    is_available   = models.BooleanField(
        default=True,
        help_text="Global kill-switch. False = never available regardless of flags.",
    )
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = _("feature")
        verbose_name_plural = _("features")
        ordering            = ["category", "name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


# ─────────────────────────────────────────────────────────────
#  2.  FeatureFlag  — runtime on/off gate
# ─────────────────────────────────────────────────────────────

class FeatureFlag(models.Model):
    """
    One row per feature; controls whether the feature is live.

    rollout_percentage:
      0   = feature is disabled (even if is_enabled=True, no traffic)
      100 = fully enabled (default)
      1-99 = gradual rollout (checked via hash(user_id) % 100 in services.py)

    Cached aggressively — see cache.py FEATURE_CACHE_TTL.
    """
    id                  = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    feature             = models.OneToOneField(Feature, on_delete=models.CASCADE,
                                               related_name="flag")
    is_enabled          = models.BooleanField(default=False, db_index=True)
    rollout_percentage  = models.PositiveSmallIntegerField(
        default=100,
        help_text="0=disabled, 100=all users, 1-99=gradual rollout.",
    )
    enabled_at          = models.DateTimeField(null=True, blank=True)
    disabled_at         = models.DateTimeField(null=True, blank=True)
    enabled_by          = models.ForeignKey(
        "accounts.User", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="feature_flags_enabled",
    )
    notes               = models.TextField(blank=True)
    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = _("feature flag")
        verbose_name_plural = _("feature flags")

    def __str__(self):
        state = "ON" if self.is_enabled else "OFF"
        return f"{self.feature.code} [{state}]"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        _invalidate_feature_cache(self.feature.code)

    def delete(self, *args, **kwargs):
        code = self.feature.code
        super().delete(*args, **kwargs)
        _invalidate_feature_cache(code)


# ─────────────────────────────────────────────────────────────
#  3.  ProviderConfig  — credentials / settings for a feature's provider
# ─────────────────────────────────────────────────────────────

class ProviderConfig(models.Model):
    """
    Stores provider credentials / settings for a specific feature.

    A feature may have multiple providers (e.g. payment_gateway → stripe | cashfree).
    Only one ProviderConfig per (feature, provider_key) should be active.

    config (JSONField):
      Stores arbitrary key-value pairs as defined by Feature.config_schema.
      IMPORTANT: In production, encrypt sensitive values using
      django-encrypted-model-fields or AWS Secrets Manager.

    Example:
      feature = Feature(code="payment_stripe")
      provider_key = "stripe"
      config = {
          "STRIPE_SECRET_KEY": "sk_live_...",
          "STRIPE_WEBHOOK_SECRET": "whsec_..."
      }
    """
    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    feature         = models.ForeignKey(Feature, on_delete=models.CASCADE,
                                        related_name="provider_configs")
    provider_key    = models.SlugField(max_length=60,
                                       help_text="Provider slug, e.g. 'stripe', 'cashfree'.")
    config          = models.JSONField(default=dict, help_text="Provider credentials/settings.")
    is_active       = models.BooleanField(default=False, db_index=True)
    created_by      = models.ForeignKey(
        "accounts.User", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="provider_configs",
    )
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = _("provider config")
        verbose_name_plural = _("provider configs")
        unique_together     = [("feature", "provider_key")]
        ordering            = ["feature__code", "provider_key"]

    def __str__(self):
        state = "active" if self.is_active else "inactive"
        return f"{self.feature.code} / {self.provider_key} [{state}]"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        _invalidate_provider_config_cache(self.feature.code, self.provider_key)

    def delete(self, *args, **kwargs):
        fcode, pkey = self.feature.code, self.provider_key
        super().delete(*args, **kwargs)
        _invalidate_provider_config_cache(fcode, pkey)

    def masked_config(self) -> dict:
        """Return config with secret values masked for display."""
        schema = self.feature.config_schema or {}
        return {
            k: "••••••" if schema.get(k, {}).get("secret") else v
            for k, v in self.config.items()
        }


# ─────────────────────────────────────────────────────────────
#  4.  AppSetting  — general key-value store
# ─────────────────────────────────────────────────────────────

class AppSetting(models.Model):
    """
    Site-wide key-value settings store.

    is_public = True → safe to expose via public API (e.g. currency, brand name).
    is_public = False → internal only (e.g. fee rates, limits).

    Supports typed values (coerced on read via AppSetting.typed_value property).

    Example keys:
      site_name          → "Aurora Blings"             (string, public)
      default_currency   → "INR"                       (string, public)
      max_cart_items     → "20"                        (integer)
      cash_on_delivery   → "true"                      (boolean)
      homepage_banner    → {"url": "...", "cta": "..."}(json)
    """
    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key          = models.SlugField(max_length=100, unique=True, db_index=True)
    value        = models.TextField(blank=True)
    value_type   = models.CharField(max_length=10, choices=SettingType.choices,
                                    default=SettingType.STRING)
    category     = models.CharField(max_length=20, choices=SettingCategory.choices,
                                    default=SettingCategory.GENERAL)
    label        = models.CharField(max_length=200, blank=True,
                                    help_text="Human-readable display label.")
    description  = models.TextField(blank=True)
    is_public    = models.BooleanField(
        default=False,
        help_text="If True, exposed via the public /settings/ endpoint.",
    )
    is_editable  = models.BooleanField(
        default=True,
        help_text="Set False to lock a setting against admin edits.",
    )
    updated_by   = models.ForeignKey(
        "accounts.User", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="settings_updated",
    )
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = _("app setting")
        verbose_name_plural = _("app settings")
        ordering            = ["category", "key"]

    def __str__(self):
        return f"{self.key} = {self.value[:40]}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        _invalidate_setting_cache(self.key)

    def delete(self, *args, **kwargs):
        key = self.key
        super().delete(*args, **kwargs)
        _invalidate_setting_cache(key)

    @property
    def typed_value(self):
        """Return value coerced to its declared type."""
        import json
        v = self.value
        try:
            if self.value_type == SettingType.INTEGER:  return int(v)
            if self.value_type == SettingType.FLOAT:    return float(v)
            if self.value_type == SettingType.BOOLEAN:  return v.lower() in ("true", "1", "yes")
            if self.value_type == SettingType.JSON:     return json.loads(v)
        except (ValueError, TypeError):
            pass
        return v


# ─────────────────────────────────────────────────────────────
#  Cache invalidation helpers (module-level, no circular import)
# ─────────────────────────────────────────────────────────────

def _invalidate_feature_cache(code: str) -> None:
    cache.delete(f"feature:flag:{code}")


def _invalidate_provider_config_cache(feature_code: str, provider_key: str) -> None:
    cache.delete(f"feature:provider:{feature_code}:{provider_key}")


def _invalidate_setting_cache(key: str) -> None:
    cache.delete(f"setting:{key}")
    cache.delete("settings:all_public")  # blow the batch cache too
