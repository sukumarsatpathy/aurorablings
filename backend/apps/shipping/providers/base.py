from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProviderResponse:
    success: bool
    status: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    error_code: str = ""
    error_message: str = ""


class BaseShippingProvider:
    name: str = ""

    def authenticate(self) -> ProviderResponse:
        return ProviderResponse(success=True, data={})

    def create_order(self, order) -> ProviderResponse:
        raise NotImplementedError

    def assign_awb(self, shipment) -> ProviderResponse:
        raise NotImplementedError

    def generate_label(self, shipment) -> ProviderResponse:
        raise NotImplementedError

    def generate_manifest(self, shipment) -> ProviderResponse:
        raise NotImplementedError

    def request_pickup(self, shipment) -> ProviderResponse:
        raise NotImplementedError

    def cancel_shipment(self, shipment) -> ProviderResponse:
        raise NotImplementedError

    def get_tracking(self, shipment) -> ProviderResponse:
        raise NotImplementedError

    def verify_serviceability(self, order_or_address) -> ProviderResponse:
        raise NotImplementedError

    def normalize_status(self, payload: dict[str, Any]) -> str:
        raise NotImplementedError

    def build_event_idempotency_key(self, payload: dict[str, Any]) -> str:
        return ""
