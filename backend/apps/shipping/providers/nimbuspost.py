from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

import requests
from django.conf import settings

from core.logging import get_logger
from apps.shipping.models import ShipmentStatus

from .base import BaseShippingProvider, ProviderResponse

logger = get_logger(__name__)


class NimbusPostProvider(BaseShippingProvider):
    name = "nimbuspost"

    STATUS_MAP = {
        "pending": ShipmentStatus.PENDING_APPROVAL,
        "approved": ShipmentStatus.APPROVED,
        "booked": ShipmentStatus.BOOKED,
        "manifested": ShipmentStatus.BOOKED,
        "picked": ShipmentStatus.PICKED_UP,
        "picked_up": ShipmentStatus.PICKED_UP,
        "in_transit": ShipmentStatus.IN_TRANSIT,
        "ofd": ShipmentStatus.OUT_FOR_DELIVERY,
        "out_for_delivery": ShipmentStatus.OUT_FOR_DELIVERY,
        "delivered": ShipmentStatus.DELIVERED,
        "failed": ShipmentStatus.FAILED,
        "cancelled": ShipmentStatus.CANCELLED,
        "rto": ShipmentStatus.RTO,
        "returned": ShipmentStatus.RETURNED,
        "exception": ShipmentStatus.EXCEPTION,
    }

    def _base_url(self) -> str:
        return str(getattr(settings, "NIMBUSPOST_BASE_URL", "https://api.nimbuspost.com/v1").rstrip("/"))

    def _api_key(self) -> str:
        return str(getattr(settings, "NIMBUSPOST_API_KEY", "")).strip()

    def _timeout(self) -> int:
        return int(getattr(settings, "NIMBUSPOST_TIMEOUT_SECONDS", 20))

    def _headers(self) -> dict[str, str]:
        api_key = self._api_key()
        if not api_key:
            return {}
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

    def _request(self, *, method: str, path: str, payload: dict[str, Any] | None = None, params: dict[str, Any] | None = None) -> ProviderResponse:
        if not self._api_key():
            return ProviderResponse(success=False, error_code="config_error", error_message="NimbusPost API key is not configured.")

        url = f"{self._base_url()}{path}"
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self._headers(),
                json=payload,
                params=params,
                timeout=self._timeout(),
            )
            response.raise_for_status()
            data = response.json() if response.content else {}
            return ProviderResponse(success=True, data=data)
        except requests.RequestException as exc:
            logger.warning("nimbuspost_request_failed", method=method, path=path, error=str(exc))
            return ProviderResponse(success=False, error_code="provider_temporary_failure", error_message=str(exc))
        except ValueError:
            return ProviderResponse(success=True, data={})

    def authenticate(self) -> ProviderResponse:
        if not self._api_key():
            return ProviderResponse(success=False, error_code="config_error", error_message="NimbusPost API key is not configured.")
        return ProviderResponse(success=True, data={"token": "***"})

    def _build_order_payload(self, order) -> dict[str, Any]:
        shipping = order.shipping_address or {}
        return {
            "order_number": order.order_number,
            "payment_method": order.payment_method,
            "order_amount": str(order.grand_total),
            "order_items": [
                {
                    "name": item.product_name,
                    "sku": item.sku,
                    "units": int(item.quantity),
                    "selling_price": str(item.unit_price),
                }
                for item in order.items.all()
            ],
            "consignee": {
                "name": shipping.get("full_name") or "Customer",
                "address1": shipping.get("line1") or "",
                "address2": shipping.get("line2") or "",
                "city": shipping.get("city") or "",
                "state": shipping.get("state") or "",
                "pincode": shipping.get("pincode") or "",
                "country": shipping.get("country") or "India",
                "phone": shipping.get("phone") or "",
                "email": (order.user.email if order.user else order.guest_email) or "",
            },
        }

    def create_order(self, order) -> ProviderResponse:
        payload = self._build_order_payload(order)
        # Endpoint can be changed from one place if NimbusPost updates path.
        result = self._request(method="POST", path="/shipments", payload=payload)
        if not result.success:
            return result
        body = result.data or {}
        shipment_data = body.get("data") or body
        return ProviderResponse(
            success=True,
            status=ShipmentStatus.BOOKED,
            data={
                "external_order_id": str(shipment_data.get("order_id") or order.order_number),
                "external_shipment_id": str(shipment_data.get("shipment_id") or shipment_data.get("id") or ""),
                "awb_code": str(shipment_data.get("awb_number") or ""),
                "courier_name": str(shipment_data.get("courier_name") or ""),
                "tracking_url": str(shipment_data.get("tracking_url") or ""),
                "label_url": str(shipment_data.get("label_url") or ""),
                "raw": body,
            },
        )

    def assign_awb(self, shipment) -> ProviderResponse:
        # Nimbus usually returns AWB at booking; keep this hook for compatibility.
        awb = str(shipment.awb_code or "")
        return ProviderResponse(
            success=True,
            status=ShipmentStatus.AWB_ASSIGNED if awb else ShipmentStatus.BOOKED,
            data={"awb_code": awb, "courier_name": shipment.courier_name or "", "raw": {}},
        )

    def generate_label(self, shipment) -> ProviderResponse:
        if shipment.label_url:
            return ProviderResponse(success=True, data={"label_url": shipment.label_url, "raw": {}})
        if not shipment.external_shipment_id:
            return ProviderResponse(success=False, error_code="validation_error", error_message="Missing external shipment ID")
        result = self._request(method="GET", path=f"/shipments/{shipment.external_shipment_id}/label")
        if not result.success:
            return result
        data = result.data or {}
        return ProviderResponse(success=True, data={"label_url": str((data.get("data") or data).get("label_url") or ""), "raw": data})

    def generate_manifest(self, shipment) -> ProviderResponse:
        return ProviderResponse(success=True, data={"manifest_url": shipment.manifest_url or "", "raw": {}})

    def request_pickup(self, shipment) -> ProviderResponse:
        if not shipment.external_shipment_id:
            return ProviderResponse(success=False, error_code="validation_error", error_message="Missing external shipment ID")
        result = self._request(method="POST", path=f"/shipments/{shipment.external_shipment_id}/pickup")
        if not result.success:
            return result
        return ProviderResponse(success=True, status=ShipmentStatus.PICKUP_REQUESTED, data={"raw": result.data or {}})

    def cancel_shipment(self, shipment) -> ProviderResponse:
        if not shipment.external_shipment_id:
            return ProviderResponse(success=False, error_code="validation_error", error_message="Missing external shipment ID")
        result = self._request(method="POST", path=f"/shipments/{shipment.external_shipment_id}/cancel")
        if not result.success:
            return result
        return ProviderResponse(success=True, status=ShipmentStatus.CANCELLED, data={"raw": result.data or {}})

    def get_tracking(self, shipment) -> ProviderResponse:
        if not shipment.awb_code and not shipment.external_shipment_id:
            return ProviderResponse(success=False, error_code="validation_error", error_message="Missing AWB or external shipment ID")
        path = f"/tracking/{shipment.awb_code}" if shipment.awb_code else f"/shipments/{shipment.external_shipment_id}/tracking"
        result = self._request(method="GET", path=path)
        if not result.success:
            return result
        data = result.data or {}
        track = data.get("data") or data
        status_text = str(track.get("status") or track.get("current_status") or "")
        return ProviderResponse(
            success=True,
            status=self.normalize_status(track),
            data={
                "provider_status": status_text,
                "tracking_url": str(track.get("tracking_url") or ""),
                "event": track,
                "raw": data,
            },
        )

    def verify_serviceability(self, order_or_address) -> ProviderResponse:
        address = order_or_address.shipping_address if hasattr(order_or_address, "shipping_address") else (order_or_address or {})
        pincode = str(address.get("pincode") or "").strip()
        if not pincode:
            return ProviderResponse(success=False, error_code="validation_error", error_message="Missing destination pincode")
        result = self._request(method="GET", path="/serviceability", params={"pincode": pincode})
        if not result.success:
            return result
        return ProviderResponse(success=True, data={"raw": result.data or {}})

    def normalize_status(self, payload: dict[str, Any]) -> str:
        status = str(payload.get("status") or payload.get("current_status") or payload.get("shipment_status") or "").strip().lower()
        normalized = status.replace(" ", "_")
        return self.STATUS_MAP.get(normalized, ShipmentStatus.IN_TRANSIT if normalized else ShipmentStatus.BOOKED)

    @classmethod
    def build_event_idempotency_key(cls, payload: dict[str, Any]) -> str:
        body = json.dumps(payload or {}, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
        return f"nimbuspost:{digest}"

    @staticmethod
    def verify_webhook_signature(*, body: bytes, signature: str) -> bool:
        secret = str(getattr(settings, "NIMBUSPOST_WEBHOOK_SECRET", "") or "")
        if not secret:
            return True
        if not signature:
            return False
        expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)
