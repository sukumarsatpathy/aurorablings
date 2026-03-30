from rest_framework import serializers

from .models import Shipment, ShipmentEvent


class ShipmentEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShipmentEvent
        fields = [
            "id",
            "source",
            "provider_status",
            "internal_status",
            "event_payload",
            "created_at",
        ]
        read_only_fields = fields


class ShipmentSerializer(serializers.ModelSerializer):
    events = ShipmentEventSerializer(many=True, read_only=True)
    order_id = serializers.UUIDField(source="order.id", read_only=True)
    order_number = serializers.CharField(source="order.order_number", read_only=True)

    class Meta:
        model = Shipment
        fields = [
            "id",
            "order_id",
            "order_number",
            "provider",
            "status",
            "external_order_id",
            "external_shipment_id",
            "awb_code",
            "courier_name",
            "courier_company_id",
            "tracking_url",
            "label_url",
            "manifest_url",
            "invoice_url",
            "pickup_requested",
            "pickup_scheduled_at",
            "shipped_at",
            "delivered_at",
            "raw_provider_response",
            "error_code",
            "error_message",
            "created_at",
            "updated_at",
            "events",
        ]
        read_only_fields = fields


class ShipmentActionSerializer(serializers.Serializer):
    order_id = serializers.UUIDField(required=False)
    shipment_id = serializers.UUIDField(required=False)
    force = serializers.BooleanField(required=False, default=False)


class TrackingWebhookSerializer(serializers.Serializer):
    payload = serializers.JSONField(required=False)
