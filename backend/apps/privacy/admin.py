from django.contrib import admin
from django.utils.html import format_html

from .models import ConsentStatus, CookieConsentLog


class ConsentStatusQuickFilter(admin.SimpleListFilter):
    title = "Consent quick filters"
    parameter_name = "consent_quick"

    def lookups(self, request, model_admin):
        return (
            ("accepted", "Accepted"),
            ("rejected", "Rejected"),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == "accepted":
            return queryset.filter(consent_status=ConsentStatus.ACCEPTED_ALL)
        if value == "rejected":
            return queryset.filter(consent_status=ConsentStatus.REJECTED_ALL)
        return queryset


@admin.register(CookieConsentLog)
class CookieConsentLogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "consent_status_badge",
        "user",
        "anonymous_id",
        "category_analytics_flag",
        "category_marketing_flag",
        "category_preferences_flag",
        "created_at",
    )
    list_filter = (
        ConsentStatusQuickFilter,
        "consent_status",
        "created_at",
        "category_analytics",
        "category_marketing",
    )
    search_fields = ("anonymous_id", "user__email")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]

    @admin.display(description="Status")
    def consent_status_badge(self, obj: CookieConsentLog):
        palette = {
            ConsentStatus.ACCEPTED_ALL: ("#eaf7ed", "#2e7d32"),
            ConsentStatus.REJECTED_ALL: ("#fdecea", "#c62828"),
            ConsentStatus.CUSTOMIZED: ("#fff8e1", "#f57f17"),
        }
        bg, fg = palette.get(obj.consent_status, ("#f3f4f6", "#374151"))
        label = obj.get_consent_status_display()
        return format_html(
            '<span style="background:{};color:{};padding:2px 8px;border-radius:999px;font-weight:600;">{}</span>',
            bg,
            fg,
            label,
        )

    @admin.display(boolean=True, description="Analytics")
    def category_analytics_flag(self, obj: CookieConsentLog):
        return obj.category_analytics

    @admin.display(boolean=True, description="Marketing")
    def category_marketing_flag(self, obj: CookieConsentLog):
        return obj.category_marketing

    @admin.display(boolean=True, description="Preferences")
    def category_preferences_flag(self, obj: CookieConsentLog):
        return obj.category_preferences
