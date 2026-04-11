from __future__ import annotations

from .base import BaseShippingProvider, ProviderResponse
from apps.shipping.models import ShipmentStatus


class LocalDeliveryProvider(BaseShippingProvider):
    name = "local_delivery"

    def create_order(self, order) -> ProviderResponse:
        return ProviderResponse(
            success=True,
            status=ShipmentStatus.ASSIGNED,
            data={
                "external_order_id": order.order_number,
                "external_shipment_id": "",
                "raw": {"provider": "local_delivery", "message": "Assigned for local fulfillment."},
            },
        )

    def assign_awb(self, shipment) -> ProviderResponse:
        return ProviderResponse(success=True, status=ShipmentStatus.ASSIGNED, data={"raw": {}})

    def generate_label(self, shipment) -> ProviderResponse:
        return ProviderResponse(success=True, data={"label_url": "", "raw": {}})

    def generate_manifest(self, shipment) -> ProviderResponse:
        return ProviderResponse(success=True, data={"manifest_url": "", "raw": {}})

    def request_pickup(self, shipment) -> ProviderResponse:
        return ProviderResponse(success=True, status=ShipmentStatus.OUT_FOR_DELIVERY, data={"raw": {}})

    def cancel_shipment(self, shipment) -> ProviderResponse:
        return ProviderResponse(success=True, status=ShipmentStatus.CANCELLED, data={"raw": {}})

    def get_tracking(self, shipment) -> ProviderResponse:
        status = shipment.local_delivery_status or shipment.status or ShipmentStatus.ASSIGNED
        return ProviderResponse(
            success=True,
            status=status,
            data={
                "provider_status": status,
                "tracking_url": "",
                "event": {"local_status": status},
                "raw": {"provider": "local_delivery", "status": status},
            },
        )

    def verify_serviceability(self, order_or_address) -> ProviderResponse:
        return ProviderResponse(success=True, data={"raw": {"provider": "local_delivery"}})

    def normalize_status(self, payload: dict) -> str:
        status = str(payload.get("status") or payload.get("local_status") or "").strip().lower().replace(" ", "_")
        if status in {ShipmentStatus.ASSIGNED, ShipmentStatus.OUT_FOR_DELIVERY, ShipmentStatus.DELIVERED, ShipmentStatus.CANCELLED}:
            return status
        return ShipmentStatus.ASSIGNED
