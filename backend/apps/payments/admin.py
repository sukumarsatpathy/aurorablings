from django.contrib import admin
from django.utils.html import format_html
from .models import PaymentTransaction, WebhookLog, WebhookEvent, Refund, TransactionStatus

STATUS_COLOURS = {
    TransactionStatus.CREATED:   "#6366f1",
    TransactionStatus.PENDING:   "#d97706",
    TransactionStatus.SUCCESS:   "#16a34a",
    TransactionStatus.FAILED:    "#dc2626",
    TransactionStatus.REFUNDED:  "#9333ea",
    TransactionStatus.PARTIALLY_REFUNDED: "#7c3aed",
    TransactionStatus.CANCELLED: "#6b7280",
    TransactionStatus.RETRY:     "#0891b2",
}


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display   = [
        "id_short", "order_display", "provider", "status_badge",
        "amount_display", "retry_display", "created_at",
    ]
    list_filter    = ["provider", "status", "currency"]
    search_fields  = ["id", "provider_ref", "order__order_number"]
    readonly_fields = [f.name for f in PaymentTransaction._meta.fields]

    def has_add_permission(self, request):
        return False

    def id_short(self, obj):
        return str(obj.id)[:8] + "…"
    id_short.short_description = "Txn ID"

    def order_display(self, obj):
        return obj.order.order_number
    order_display.short_description = "Order"

    def status_badge(self, obj):
        colour = STATUS_COLOURS.get(obj.status, "#6b7280")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:700">{}</span>',
            colour, obj.status.upper()
        )
    status_badge.short_description = "Status"

    def amount_display(self, obj):
        return f"{obj.currency} {obj.amount}"
    amount_display.short_description = "Amount"

    def retry_display(self, obj):
        colour = "#dc2626" if obj.retry_count >= obj.max_retries else "#16a34a"
        return format_html(
            '<span style="color:{}">{}/{}</span>', colour, obj.retry_count, obj.max_retries
        )
    retry_display.short_description = "Retries"


@admin.register(WebhookLog)
class WebhookLogAdmin(admin.ModelAdmin):
    list_display  = [
        "created_at", "provider", "event_status",
        "verified_icon", "processed_icon",
        "order_ref", "provider_ref",
    ]
    list_filter   = ["provider", "is_verified", "is_processed", "event_status"]
    search_fields = ["provider_ref", "order_ref", "idempotency_key"]
    readonly_fields = [f.name for f in WebhookLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def verified_icon(self, obj):
        return format_html("✅" if obj.is_verified else "❌")
    verified_icon.short_description = "Verified"

    def processed_icon(self, obj):
        return format_html("✅" if obj.is_processed else "⏳")
    processed_icon.short_description = "Processed"


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = [
        "refund_id",
        "order",
        "payment",
        "amount",
        "status",
        "source",
        "created_at",
    ]
    list_filter = ["status", "source", "created_at"]
    search_fields = ["refund_id", "cf_refund_id", "order__order_number", "payment__provider_ref"]
    readonly_fields = [f.name for f in Refund._meta.fields]


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ["event_id", "event_type", "processed", "created_at"]
    list_filter = ["processed", "event_type", "created_at"]
    search_fields = ["event_id", "event_type"]
    readonly_fields = [f.name for f in WebhookEvent._meta.fields]
