from django.contrib import admin

from .models import Shipment, ShipmentEvent


class ShipmentEventInline(admin.TabularInline):
    model = ShipmentEvent
    extra = 0
    readonly_fields = [
        "source",
        "provider_status",
        "internal_status",
        "event_payload",
        "idempotency_key",
        "created_at",
    ]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "order",
        "provider",
        "status",
        "approved_at",
        "awb_code",
        "courier_name",
        "pickup_requested",
        "created_at",
    ]
    list_filter = ["provider", "status", "pickup_requested", "created_at"]
    search_fields = ["order__order_number", "external_order_id", "external_shipment_id", "awb_code"]
    readonly_fields = ["created_at", "updated_at", "raw_provider_response", "error_code", "error_message"]
    inlines = [ShipmentEventInline]
    actions = ["action_refresh_tracking"]

    @admin.action(description="Refresh tracking for selected shipments")
    def action_refresh_tracking(self, request, queryset):
        from . import services

        ok = 0
        for shipment in queryset:
            try:
                services.sync_tracking(shipment_id=str(shipment.id), source="manual")
                ok += 1
            except Exception:
                continue
        self.message_user(request, f"Tracking refreshed for {ok} shipment(s).")


@admin.register(ShipmentEvent)
class ShipmentEventAdmin(admin.ModelAdmin):
    list_display = ["id", "shipment", "source", "provider_status", "internal_status", "created_at"]
    list_filter = ["source", "internal_status", "created_at"]
    search_fields = ["shipment__order__order_number", "provider_status", "idempotency_key"]
    readonly_fields = ["created_at"]
