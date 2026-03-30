from django.contrib import admin
from django.utils.html import format_html
from .models import Warehouse, WarehouseStock, StockLedger, StockReservation


# ─────────────────────────────────────────────────────────────
#  Warehouse
# ─────────────────────────────────────────────────────────────

@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display  = ["name", "code", "type", "is_active", "is_default"]
    list_filter   = ["type", "is_active"]
    search_fields = ["name", "code"]
    readonly_fields = ["id"]


# ─────────────────────────────────────────────────────────────
#  Warehouse Stock
# ─────────────────────────────────────────────────────────────

@admin.register(WarehouseStock)
class WarehouseStockAdmin(admin.ModelAdmin):
    list_display  = [
        "sku_display", "warehouse_display",
        "on_hand", "reserved", "available",
        "stock_indicator", "updated_at",
    ]
    list_filter   = ["warehouse"]
    search_fields = ["variant__sku", "variant__product__name"]
    readonly_fields = ["id", "on_hand", "reserved", "available", "updated_at"]

    def sku_display(self, obj):
        return obj.variant.sku
    sku_display.short_description = "SKU"

    def warehouse_display(self, obj):
        return obj.warehouse.code
    warehouse_display.short_description = "Warehouse"

    def stock_indicator(self, obj):
        if obj.available <= 0:
            colour, label = "#dc2626", "Out of stock"
        elif obj.available <= obj.low_stock_threshold:
            colour, label = "#f59e0b", "Low stock"
        else:
            colour, label = "#16a34a", "In stock"
        return format_html(
            '<span style="color:{};font-weight:600">● {}</span>', colour, label
        )
    stock_indicator.short_description = "Status"

    actions = ["action_recompute"]

    @admin.action(description="Recompute selected stock records from ledger")
    def action_recompute(self, request, queryset):
        from .services import recompute_stock
        count = 0
        for record in queryset:
            recompute_stock(stock_record=record)
            count += 1
        self.message_user(request, f"{count} stock record(s) recomputed.")


# ─────────────────────────────────────────────────────────────
#  Stock Ledger  (read-only)
# ─────────────────────────────────────────────────────────────

@admin.register(StockLedger)
class StockLedgerAdmin(admin.ModelAdmin):
    list_display  = [
        "created_at", "sku_display", "warehouse_display",
        "movement_type", "quantity_display", "reference_type", "reference_id",
        "on_hand_after", "available_after",
    ]
    list_filter   = ["movement_type", "reference_type", "stock_record__warehouse"]
    search_fields = [
        "stock_record__variant__sku",
        "reference_id",
    ]
    readonly_fields = [f.name for f in StockLedger._meta.fields]   # all read-only
    date_hierarchy  = "created_at"

    def has_add_permission(self, request):
        return False     # never create ledger entries manually

    def has_change_permission(self, request, obj=None):
        return False     # immutable

    def sku_display(self, obj):
        return obj.stock_record.variant.sku
    sku_display.short_description = "SKU"

    def warehouse_display(self, obj):
        return obj.stock_record.warehouse.code
    warehouse_display.short_description = "Warehouse"

    def quantity_display(self, obj):
        sign  = "+" if obj.quantity >= 0 else ""
        colour = "#16a34a" if obj.quantity >= 0 else "#dc2626"
        return format_html(
            '<span style="color:{};font-weight:600">{}{}</span>',
            colour, sign, obj.quantity
        )
    quantity_display.short_description = "Δ Qty"


# ─────────────────────────────────────────────────────────────
#  Stock Reservation
# ─────────────────────────────────────────────────────────────

@admin.register(StockReservation)
class StockReservationAdmin(admin.ModelAdmin):
    list_display  = [
        "reference_id", "sku_display", "quantity",
        "status", "expires_at", "created_at",
    ]
    list_filter   = ["status", "reference_type"]
    search_fields = ["reference_id", "stock_record__variant__sku"]
    readonly_fields = ["id", "created_at", "updated_at"]

    def sku_display(self, obj):
        return obj.stock_record.variant.sku
    sku_display.short_description = "SKU"
