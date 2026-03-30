from django.contrib import admin
from django.utils.html import format_html
from .models import TaxRule, ShippingRule, FeeRule


class ActiveFilter(admin.SimpleListFilter):
    title        = "Status"
    parameter_name = "active_status"

    def lookups(self, request, model_admin):
        return [("active", "Active only"), ("inactive", "Inactive only")]

    def queryset(self, request, qs):
        if self.value() == "active":
            return qs.filter(is_active=True)
        if self.value() == "inactive":
            return qs.filter(is_active=False)
        return qs


def _active_dot(obj):
    colour = "#16a34a" if obj.is_active else "#dc2626"
    label  = "Active" if obj.is_active else "Inactive"
    return format_html(
        '<span style="color:{};font-weight:700">● {}</span>', colour, label
    )
_active_dot.short_description = "Status"


@admin.register(TaxRule)
class TaxRuleAdmin(admin.ModelAdmin):
    list_display  = ["name", "tax_type", "rate_display", _active_dot, "priority", "start_date", "end_date"]
    list_filter   = [ActiveFilter, "tax_type", "applies_to"]
    search_fields = ["name", "tax_code", "hsn_code"]
    filter_horizontal = ["categories"]
    readonly_fields   = ["id", "created_at", "updated_at"]

    fieldsets = (
        ("Rule", {"fields": ("id", "name", "description", "is_active", "priority")}),
        ("Tax Details", {"fields": ("tax_type", "tax_code", "hsn_code", "rate", "is_inclusive", "applies_to", "categories")}),
        ("Conditions", {"fields": ("conditions",), "classes": ("collapse",)}),
        ("Validity", {"fields": ("start_date", "end_date")}),
    )

    def rate_display(self, obj):
        return f"{obj.rate}%"
    rate_display.short_description = "Rate"


@admin.register(ShippingRule)
class ShippingRuleAdmin(admin.ModelAdmin):
    list_display  = ["name", "method", "carrier", "rate_summary", _active_dot, "priority"]
    list_filter   = [ActiveFilter, "method"]
    search_fields = ["name", "carrier"]
    readonly_fields = ["id", "created_at", "updated_at"]

    fieldsets = (
        ("Rule", {"fields": ("id", "name", "description", "is_active", "priority", "is_additive")}),
        ("Shipping Config", {"fields": ("method", "carrier", "estimated_days_min", "estimated_days_max")}),
        ("Rates", {"fields": ("flat_rate", "percentage_rate", "per_kg_rate", "free_threshold_amount", "max_charge")}),
        ("Conditions", {"fields": ("conditions",), "classes": ("collapse",)}),
        ("Validity", {"fields": ("start_date", "end_date")}),
    )

    def rate_summary(self, obj):
        m = obj.method
        if m == "flat":            return f"₹{obj.flat_rate}"
        if m == "percentage":      return f"{obj.percentage_rate}%"
        if m == "weight_based":    return f"₹{obj.per_kg_rate}/kg"
        if m == "free_threshold":  return f"Free above ₹{obj.free_threshold_amount}"
        return "Free"
    rate_summary.short_description = "Rate"


@admin.register(FeeRule)
class FeeRuleAdmin(admin.ModelAdmin):
    list_display  = ["name", "fee_type", "amount_summary", _active_dot, "priority"]
    list_filter   = [ActiveFilter, "fee_type", "amount_type", "is_negative"]
    search_fields = ["name"]
    readonly_fields = ["id", "created_at", "updated_at"]

    fieldsets = (
        ("Rule", {"fields": ("id", "name", "description", "is_active", "priority")}),
        ("Fee Config", {"fields": ("fee_type", "amount_type", "amount", "is_negative", "max_amount")}),
        ("Conditions", {"fields": ("conditions",), "classes": ("collapse",)}),
        ("Validity", {"fields": ("start_date", "end_date")}),
    )

    def amount_summary(self, obj):
        sign  = "−" if obj.is_negative else "+"
        value = f"{obj.amount}%" if obj.amount_type == "percentage" else f"₹{obj.amount}"
        return format_html(
            '<span style="color:{};font-weight:600">{}{}</span>',
            "#dc2626" if obj.is_negative else "#16a34a",
            sign, value,
        )
    amount_summary.short_description = "Amount"
