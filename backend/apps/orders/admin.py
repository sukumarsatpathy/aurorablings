from django.contrib import admin
from django.utils.html import format_html
from .models import Order, OrderItem, OrderStatusHistory, OrderStatus


# ─────────────────────────────────────────────────────────────
#  Status History Inline  (read-only)
# ─────────────────────────────────────────────────────────────

class OrderStatusHistoryInline(admin.TabularInline):
    model      = OrderStatusHistory
    extra      = 0
    readonly_fields = ["from_status", "to_status", "changed_by", "notes", "created_at"]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


# ─────────────────────────────────────────────────────────────
#  Order Items Inline  (read-only)
# ─────────────────────────────────────────────────────────────

class OrderItemInline(admin.TabularInline):
    model      = OrderItem
    extra      = 0
    fields     = ["sku", "product_name", "variant_name", "quantity", "unit_price", "line_total"]
    readonly_fields = ["sku", "product_name", "variant_name", "quantity", "unit_price", "line_total"]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


# ─────────────────────────────────────────────────────────────
#  Order Admin
# ─────────────────────────────────────────────────────────────

STATUS_COLOURS = {
    OrderStatus.DRAFT:      "#6b7280",
    OrderStatus.PLACED:     "#2563eb",
    OrderStatus.PAID:       "#7c3aed",
    OrderStatus.PROCESSING: "#d97706",
    OrderStatus.SHIPPED:    "#0891b2",
    OrderStatus.DELIVERED:  "#16a34a",
    OrderStatus.COMPLETED:  "#15803d",
    OrderStatus.CANCELLED:  "#dc2626",
    OrderStatus.REFUNDED:   "#9333ea",
}


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display   = [
        "order_number", "user_display", "status_badge",
        "payment_badge", "grand_total", "currency",
        "item_count_display", "invoice_links", "created_at",
    ]
    list_filter    = ["status", "payment_status", "payment_method", "created_at"]
    search_fields  = ["order_number", "user__email", "guest_email", "items__sku"]
    readonly_fields = [
        "id", "order_number", "cart_id_snapshot",
        "subtotal", "grand_total",
        "invoice_panel",
        "placed_at", "paid_at", "shipped_at", "delivered_at", "cancelled_at",
        "created_at", "updated_at",
    ]
    inlines        = [OrderItemInline, OrderStatusHistoryInline]

    fieldsets = (
        ("Order Info", {
            "fields": ("id", "order_number", "user", "guest_email", "status", "cart_id_snapshot"),
        }),
        ("Payment", {
            "fields": ("payment_status", "payment_method", "payment_reference"),
        }),
        ("Addresses", {
            "fields": ("shipping_address", "billing_address"),
            "classes": ("collapse",),
        }),
        ("Financials", {
            "fields": ("subtotal", "discount_amount", "shipping_cost", "tax_amount", "grand_total", "currency"),
        }),
        ("Invoice", {
            "fields": ("invoice_panel",),
        }),
        ("Fulfilment", {
            "fields": ("warehouse", "tracking_number", "shipping_carrier"),
        }),
        ("Notes", {
            "fields": ("notes", "internal_notes"),
            "classes": ("collapse",),
        }),
        ("Timestamps", {
            "fields": ("placed_at", "paid_at", "shipped_at", "delivered_at", "cancelled_at", "created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    actions = ["action_mark_processing", "action_mark_cancelled", "action_generate_invoices"]

    @admin.action(description="Mark selected orders as Processing")
    def action_mark_processing(self, request, queryset):
        from .services import transition_order
        count = 0
        for order in queryset.filter(status=OrderStatus.PAID):
            transition_order(order=order, new_status=OrderStatus.PROCESSING, changed_by=request.user, notes="Bulk admin action.")
            count += 1
        self.message_user(request, f"{count} order(s) moved to Processing.")

    @admin.action(description="Cancel selected orders")
    def action_mark_cancelled(self, request, queryset):
        from .services import cancel_order
        count = 0
        for order in queryset:
            if order.is_cancellable:
                cancel_order(order=order, changed_by=request.user, reason="Bulk admin cancellation.")
                count += 1
        self.message_user(request, f"{count} order(s) cancelled.")

    @admin.action(description="Generate invoices for selected orders")
    def action_generate_invoices(self, request, queryset):
        from apps.invoices.services.invoice_service import InvoiceService

        generated = 0
        for order in queryset:
            InvoiceService.get_or_generate_invoice(order=order, regenerate=False)
            generated += 1
        self.message_user(request, f"{generated} invoice(s) generated.")

    def user_display(self, obj):
        return obj.user.email if obj.user else f"guest: {obj.guest_email or '—'}"
    user_display.short_description = "Customer"

    def status_badge(self, obj):
        colour = STATUS_COLOURS.get(obj.status, "#6b7280")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600">{}</span>',
            colour, obj.get_status_display()
        )
    status_badge.short_description = "Status"

    def payment_badge(self, obj):
        colour = "#16a34a" if obj.payment_status == "paid" else "#d97706"
        return format_html(
            '<span style="color:{};font-weight:600">{}</span>',
            colour, obj.get_payment_status_display()
        )
    payment_badge.short_description = "Payment"

    def item_count_display(self, obj):
        return obj.item_count
    item_count_display.short_description = "Items"

    def invoice_links(self, obj):
        from apps.invoices.services.invoice_service import InvoiceService

        invoice_url = InvoiceService.build_invoice_url(order_id=str(obj.id))
        return format_html('<a href="{}" target="_blank">Download Invoice</a>', invoice_url)

    invoice_links.short_description = "Invoice"

    def invoice_panel(self, obj):
        from apps.invoices.services.invoice_service import InvoiceService

        if not obj:
            return "-"
        invoice_url = InvoiceService.build_invoice_url(order_id=str(obj.id))
        return format_html(
            '<a href="{}" target="_blank">Download Invoice</a>',
            invoice_url,
        )

    invoice_panel.short_description = "Invoice"
