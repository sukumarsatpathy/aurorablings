from django.contrib import admin
from django import forms
from django.utils.html import format_html
from django.utils import timezone

from .models import Feature, FeatureFlag, ProviderConfig, AppSetting
from . import services
from .security import is_secret_setting, mask_setting_value, MASKED_SETTING_VALUE

# ─────────────────────────────────────────────────────────────
#  Feature + FeatureFlag
# ─────────────────────────────────────────────────────────────

class FeatureFlagInline(admin.StackedInline):
    model   = FeatureFlag
    extra   = 0
    fields  = ["is_enabled", "rollout_percentage", "notes", "enabled_at", "disabled_at"]
    readonly_fields = ["enabled_at", "disabled_at"]

    def has_add_permission(self, request, obj=None): return obj is not None
    def has_delete_permission(self, request, obj=None): return False


class ProviderConfigInline(admin.TabularInline):
    model   = ProviderConfig
    extra   = 0
    fields  = ["provider_key", "is_active", "updated_at"]
    readonly_fields = ["updated_at"]


@admin.register(Feature)
class FeatureAdmin(admin.ModelAdmin):
    list_display  = ["code", "name", "category_badge", "tier_badge", "flag_status", "is_available"]
    list_filter   = ["category", "tier", "is_available"]
    search_fields = ["code", "name"]
    readonly_fields = ["id", "created_at", "updated_at"]
    inlines       = [FeatureFlagInline, ProviderConfigInline]

    actions       = ["enable_selected", "disable_selected"]

    def category_badge(self, obj):
        colours = {"payment": "#2563eb", "notification": "#7c3aed", "shipping": "#0891b2",
                   "catalog": "#16a34a", "order": "#d97706", "analytics": "#6b7280",
                   "security": "#dc2626", "general": "#9ca3af"}
        c = colours.get(obj.category, "#9ca3af")
        return format_html('<span style="color:{};font-weight:600">{}</span>', c, obj.category)
    category_badge.short_description = "Category"

    def tier_badge(self, obj):
        colours = {"free": "#16a34a", "basic": "#0891b2", "premium": "#7c3aed", "enterprise": "#d97706"}
        c = colours.get(obj.tier, "#9ca3af")
        return format_html('<span style="background:{};color:#fff;padding:1px 6px;border-radius:3px;font-size:11px">{}</span>', c, obj.tier)
    tier_badge.short_description = "Tier"

    def flag_status(self, obj):
        try:
            flag = obj.flag
            on   = flag.is_enabled and obj.is_available
            pct  = flag.rollout_percentage
            label = f"ON ({pct}%)" if on else "OFF"
            colour = "#16a34a" if on else "#dc2626"
        except FeatureFlag.DoesNotExist:
            label, colour = "NO FLAG", "#9ca3af"
        return format_html('<span style="color:{};font-weight:700">{}</span>', colour, label)
    flag_status.short_description = "Status"

    def enable_selected(self, request, queryset):
        for feature in queryset:
            services.enable_feature(feature.code, by_user=request.user, notes="Bulk enabled via admin.")
        self.message_user(request, f"{queryset.count()} feature(s) enabled.")
    enable_selected.short_description = "Enable selected features"

    def disable_selected(self, request, queryset):
        for feature in queryset:
            services.disable_feature(feature.code, by_user=request.user, notes="Bulk disabled via admin.")
        self.message_user(request, f"{queryset.count()} feature(s) disabled.")
    disable_selected.short_description = "Disable selected features"


# ─────────────────────────────────────────────────────────────
#  ProviderConfig
# ─────────────────────────────────────────────────────────────

@admin.register(ProviderConfig)
class ProviderConfigAdmin(admin.ModelAdmin):
    list_display  = ["feature_code", "provider_key", "is_active", "updated_at"]
    list_filter   = ["is_active", "feature__category"]
    search_fields = ["feature__code", "provider_key"]
    readonly_fields = ["id", "created_at", "updated_at", "masked_config_display"]

    def feature_code(self, obj): return obj.feature.code
    feature_code.short_description = "Feature"

    def masked_config_display(self, obj):
        import json
        return json.dumps(obj.masked_config(), indent=2)
    masked_config_display.short_description = "Config (masked)"

    fieldsets = (
        ("Provider", {"fields": ("id", "feature", "provider_key", "is_active")}),
        ("Config (write-only)", {"fields": ("config",), "classes": ("collapse",),
                                  "description": "Secrets are masked in the display above."}),
        ("Display", {"fields": ("masked_config_display",)}),
        ("Meta", {"fields": ("created_by", "created_at", "updated_at")}),
    )


# ─────────────────────────────────────────────────────────────
#  AppSetting
# ─────────────────────────────────────────────────────────────

@admin.register(AppSetting)
class AppSettingAdmin(admin.ModelAdmin):
    list_display  = ["key", "label", "type_badge", "category", "value_preview", "is_public", "is_editable", "updated_at"]
    list_filter   = ["category", "value_type", "is_public", "is_editable"]
    search_fields = ["key", "label", "value"]
    readonly_fields = ["id", "typed_value_display", "created_at", "updated_at"]

    fieldsets = (
        ("Setting", {"fields": ("id", "key", "label", "category", "description")}),
        ("Value",   {"fields": ("value", "value_type", "typed_value_display")}),
        ("Access",  {"fields": ("is_public", "is_editable")}),
        ("Meta",    {"fields": ("updated_by", "created_at", "updated_at")}),
    )

    def type_badge(self, obj):
        colours = {"string": "#6b7280", "integer": "#2563eb", "float": "#0891b2",
                   "boolean": "#16a34a", "json": "#7c3aed", "text": "#d97706"}
        c = colours.get(obj.value_type, "#9ca3af")
        return format_html('<span style="background:{};color:#fff;padding:1px 5px;border-radius:3px;font-size:10px">{}</span>', c, obj.value_type)
    type_badge.short_description = "Type"

    def value_preview(self, obj):
        if is_secret_setting(obj.key):
            return MASKED_SETTING_VALUE
        v = str(obj.value)
        return v[:60] + "…" if len(v) > 60 else v
    value_preview.short_description = "Value"

    def typed_value_display(self, obj):
        return mask_setting_value(obj.key, obj.typed_value)
    typed_value_display.short_description = "Typed Value (computed)"

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        value_field = form.base_fields.get("value")
        if value_field and obj and is_secret_setting(obj.key):
            value_field.widget = forms.PasswordInput(render_value=False)
            value_field.help_text = (
                "Secret value is hidden. Leave blank to keep existing value, or enter a new value to replace it."
            )
        return form

    def save_model(self, request, obj, form, change):
        if change and is_secret_setting(obj.key) and not str(obj.value or "").strip():
            previous = AppSetting.objects.filter(pk=obj.pk).values_list("value", flat=True).first()
            if previous is not None:
                obj.value = previous
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
