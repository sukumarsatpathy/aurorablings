from django.contrib import admin

from apps.pos.models import POSCashMovement, POSShift, POSTerminal


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
