from django.contrib import admin
from django.utils.html import format_html
from .models import (
    ReturnRequest, ReturnItem, ExchangeRequest, ExchangeItem,
    ReturnStatusHistory, ReturnPolicy, ReturnStatus, ExchangeStatus,
)

STATUS_COLOURS = {
    "submitted":                "#6b7280",
    "under_review":             "#d97706",
    "approved":                 "#2563eb",
    "rejected":                 "#dc2626",
    "items_received":           "#0891b2",
    "inspected":                "#7c3aed",
    "rejected_after_inspection":"#ef4444",
    "refund_initiated":         "#f59e0b",
    "exchange_shipped":         "#0891b2",
    "completed":                "#16a34a",
}


def _status_badge(obj):
    colour = STATUS_COLOURS.get(obj.status, "#6b7280")
    return format_html(
        '<span style="background:{};color:#fff;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:700">{}</span>',
        colour, obj.status.replace("_", " ").upper()
    )
_status_badge.short_description = "Status"


class ReturnItemInline(admin.TabularInline):
    model     = ReturnItem
    extra     = 0
    readonly_fields = ["order_item", "variant", "quantity", "reason_code", "condition", "unit_price", "refund_amount", "stock_reintegrated"]
    can_delete = False
    def has_add_permission(self, request, obj=None): return False


class ReturnHistoryInline(admin.TabularInline):
    model      = ReturnStatusHistory
    extra      = 0
    fk_name    = "return_request"
    readonly_fields = ["from_status", "to_status", "changed_by", "notes", "created_at"]
    can_delete = False
    def has_add_permission(self, request, obj=None): return False


@admin.register(ReturnRequest)
class ReturnRequestAdmin(admin.ModelAdmin):
    list_display  = ["return_number", "order_display", _status_badge, "is_refund_ready", "refund_amount", "created_at"]
    list_filter   = ["status", "is_refund_ready"]
    search_fields = ["return_number", "order__order_number", "user__email"]
    readonly_fields = ["id", "return_number", "refund_amount", "restocking_fee_applied",
                       "is_refund_ready", "approved_at", "items_received_at",
                       "inspected_at", "refund_initiated_at", "completed_at", "created_at", "updated_at"]
    inlines = [ReturnItemInline, ReturnHistoryInline]

    def order_display(self, obj): return obj.order.order_number
    order_display.short_description = "Order"


class ExchangeItemInline(admin.TabularInline):
    model      = ExchangeItem
    extra      = 0
    readonly_fields = ["order_item", "original_variant", "replacement_variant", "quantity", "reason_code", "condition", "price_difference", "stock_reintegrated"]
    can_delete = False
    def has_add_permission(self, request, obj=None): return False


class ExchangeHistoryInline(admin.TabularInline):
    model   = ReturnStatusHistory
    extra   = 0
    fk_name = "exchange_request"
    readonly_fields = ["from_status", "to_status", "changed_by", "notes", "created_at"]
    can_delete = False
    def has_add_permission(self, request, obj=None): return False


@admin.register(ExchangeRequest)
class ExchangeRequestAdmin(admin.ModelAdmin):
    list_display  = ["exchange_number", "order_display", _status_badge, "exchange_tracking_no", "created_at"]
    list_filter   = ["status"]
    search_fields = ["exchange_number", "order__order_number", "user__email"]
    readonly_fields = ["id", "exchange_number", "approved_at", "items_received_at",
                       "inspected_at", "exchange_shipped_at", "completed_at", "created_at", "updated_at"]
    inlines = [ExchangeItemInline, ExchangeHistoryInline]

    def order_display(self, obj): return obj.order.order_number
    order_display.short_description = "Order"


@admin.register(ReturnPolicy)
class ReturnPolicyAdmin(admin.ModelAdmin):
    list_display = ["name", "max_return_days", "max_exchange_days", "restocking_fee_pct", "is_active"]
    readonly_fields = ["created_at", "updated_at"]
