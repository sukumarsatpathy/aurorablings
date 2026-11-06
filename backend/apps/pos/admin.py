from django.contrib import admin

from apps.pos.models import (
    POSCashMovement, POSExpense, POSQuickItem, POSQuickSaleLine, POSShift, POSTerminal,
)


@admin.register(POSTerminal)
class POSTerminalAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "location", "is_active")
    search_fields = ("code", "name")


@admin.register(POSShift)
class POSShiftAdmin(admin.ModelAdmin):
    list_display = ("terminal", "status", "opened_by", "opened_at", "closed_at",
                    "opening_float", "expected_cash", "counted_cash", "variance")
    list_filter = ("status", "terminal")
    readonly_fields = ("opened_at", "closed_at", "expected_cash", "variance")


@admin.register(POSCashMovement)
class POSCashMovementAdmin(admin.ModelAdmin):
    list_display = ("shift", "movement_type", "amount", "reason", "created_by", "created_at")
    list_filter = ("movement_type",)


@admin.register(POSQuickItem)
class POSQuickItemAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "quantity", "is_active", "created_by", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(POSQuickSaleLine)
class POSQuickSaleLineAdmin(admin.ModelAdmin):
    list_display = ("quick_item", "order", "quantity", "restocked_at", "created_at")
    readonly_fields = ("order", "order_item", "quick_item", "quantity", "restocked_at", "created_at")


@admin.register(POSExpense)
class POSExpenseAdmin(admin.ModelAdmin):
    list_display = ("created_at", "payment_mode", "amount", "remarks", "shift", "created_by", "voided_at")
    list_filter = ("payment_mode",)
    search_fields = ("remarks", "upi_reference")
    readonly_fields = ("cash_movement", "void_movement", "created_at", "voided_at", "voided_by")
