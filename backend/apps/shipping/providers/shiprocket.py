from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from typing import Any

import requests
from django.core.cache import cache
from django.utils import timezone

from apps.features import services as feature_services
from core.logging import get_logger

from apps.shipping.models import ShipmentStatus
from .base import BaseShippingProvider, ProviderResponse

logger = get_logger(__name__)


class ShiprocketProvider(BaseShippingProvider):
    name = "shiprocket"

    AUTH_CACHE_KEY = "shipping:shiprocket:auth_token"
    AUTH_TTL_BUFFER_SECONDS = 120

    STATUS_MAP = {
        "new": ShipmentStatus.CREATED,
        "created": ShipmentStatus.CREATED,
        "awb assigned": ShipmentStatus.AWB_ASSIGNED,
        "pickup generated": ShipmentStatus.PICKUP_REQUESTED,
        "pickup scheduled": ShipmentStatus.PICKUP_REQUESTED,
        "picked up": ShipmentStatus.PICKED_UP,
        "in transit": ShipmentStatus.IN_TRANSIT,
        "out for delivery": ShipmentStatus.OUT_FOR_DELIVERY,
        "delivered": ShipmentStatus.DELIVERED,
        "rto initiated": ShipmentStatus.RTO,
        "rto delivered": ShipmentStatus.RTO,
        "cancelled": ShipmentStatus.CANCELLED,
        "failed": ShipmentStatus.FAILED,
        "undelivered": ShipmentStatus.EXCEPTION,
        "lost": ShipmentStatus.EXCEPTION,
    }

    def _provider_settings(self) -> dict[str, Any]:
        return feature_services.get_setting("shipping.provider", default={}) or {}

    def _settings(self) -> dict[str, Any]:
        return feature_services.get_setting("shipping.shiprocket", default={}) or {}

    def _base_url(self) -> str:
        cfg = self._settings()
        return "https://apiv2.shiprocket.in" if not cfg.get("sandbox_mode") else "https://apiv2.shiprocket.in"

    def _credentials(self) -> tuple[str, str]:
        cfg = self._settings()
        return str(cfg.get("api_user_email", "") or ""), str(cfg.get("api_user_password", "") or "")

    def _token_cached(self) -> str:
        token = cache.get(self.AUTH_CACHE_KEY)
        return str(token or "")

    def authenticate(self) -> ProviderResponse:
        cached = self._token_cached()
        if cached:
            return ProviderResponse(success=True, data={"token": cached})

        email, password = self._credentials()
        if not email or not password:
            return ProviderResponse(
                success=False,
                error_code="config_error",
                error_message="Shiprocket credentials are not configured.",
            )

        payload = {"email": email, "password": password}
        try:
            response = requests.post(
                f"{self._base_url()}/v1/external/auth/login",
                json=payload,
                timeout=20,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            logger.error("shiprocket_auth_failed", error=str(exc))
            return ProviderResponse(success=False, error_code="auth_error", error_message=str(exc))

        token = data.get("token")
        if not token:
            return ProviderResponse(
                success=False,
                error_code="auth_error",
                error_message="Shiprocket auth did not return a token.",
            )

        expires_in = int(self._settings().get("token_ttl_seconds") or 86400)
        ttl = max(300, expires_in - self.AUTH_TTL_BUFFER_SECONDS)
        cache.set(self.AUTH_CACHE_KEY, token, ttl)
        return ProviderResponse(success=True, data={"token": token})

    def refresh_token(self) -> ProviderResponse:
        cache.delete(self.AUTH_CACHE_KEY)
        return self.authenticate()

    def _request(
        self,
        *,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
        retry_on_auth: bool = True,
    ) -> ProviderResponse:
        auth_result = self.authenticate()
        if not auth_result.success:
            return auth_result

        token = auth_result.data.get("token", "")
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        url = f"{self._base_url()}{path}"

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=payload,
                timeout=25,
            )
            if response.status_code == 401 and retry_on_auth:
                self.refresh_token()
                return self._request(
                    method=method,
                    path=path,
                    params=params,
                    payload=payload,
                    retry_on_auth=False,
                )
            response.raise_for_status()
            data = response.json() if response.content else {}
        except requests.RequestException as exc:
            logger.warning(
                "shiprocket_request_failed",
                action=path,
                method=method,
                error=str(exc),
            )
            return ProviderResponse(success=False, error_code="provider_temporary_failure", error_message=str(exc))
        except ValueError:
            data = {}

        logger.info("shiprocket_request_ok", action=path, method=method)
        return ProviderResponse(success=True, data=data)

    def _build_order_payload(self, order) -> dict[str, Any]:
        shipping = order.shipping_address or {}
        billing = order.billing_address or shipping
        payment_prepaid = str(self._settings().get("default_payment_method_prepaid", "Prepaid") or "Prepaid")
        payment_cod = str(self._settings().get("default_payment_method_cod", "COD") or "COD")
        payment_method = payment_cod if str(order.payment_method).lower() == "cod" else payment_prepaid
        now = timezone.localtime()

        weight_default = float((self._provider_settings().get("default_package") or {}).get("weight_kg") or 0.3)
        length_default = float((self._provider_settings().get("default_package") or {}).get("length_cm") or 12)
        breadth_default = float((self._provider_settings().get("default_package") or {}).get("breadth_cm") or 12)
        height_default = float((self._provider_settings().get("default_package") or {}).get("height_cm") or 4)

        items = []
        for item in order.items.all():
            snapshot = item.product_snapshot or {}
            item_weight_kg = float(snapshot.get("weight_grams") or 0) / 1000 if snapshot.get("weight_grams") else weight_default
            items.append(
                {
                    "name": item.product_name,
                    "sku": item.sku,
                    "units": item.quantity,
                    "selling_price": str(item.unit_price),
                    "discount": "0",
                    "tax": "0",
                    "hsn": "",
                    "weight": max(0.05, item_weight_kg),
                }
            )

        return {
            "order_id": order.order_number,
            "order_date": now.strftime("%Y-%m-%d %H:%M"),
            "pickup_location": self._settings().get("pickup_location") or "Primary",
            "channel_id": self._settings().get("channel_id") or "",
            "billing_customer_name": billing.get("full_name") or shipping.get("full_name") or "Customer",
            "billing_last_name": "",
            "billing_address": billing.get("line1") or shipping.get("line1") or "",
            "billing_address_2": billing.get("line2") or shipping.get("line2") or "",
            "billing_city": billing.get("city") or shipping.get("city") or "",
            "billing_pincode": billing.get("pincode") or shipping.get("pincode") or "",
            "billing_state": billing.get("state") or shipping.get("state") or "",
            "billing_country": billing.get("country") or shipping.get("country") or "India",
            "billing_email": order.user.email if order.user else order.guest_email,
            "billing_phone": billing.get("phone") or shipping.get("phone") or "",
            "shipping_is_billing": True,
            "shipping_customer_name": shipping.get("full_name") or billing.get("full_name") or "Customer",
            "shipping_address": shipping.get("line1") or "",
            "shipping_address_2": shipping.get("line2") or "",
            "shipping_city": shipping.get("city") or "",
            "shipping_pincode": shipping.get("pincode") or "",
            "shipping_state": shipping.get("state") or "",
            "shipping_country": shipping.get("country") or "India",
            "shipping_email": order.user.email if order.user else order.guest_email,
            "shipping_phone": shipping.get("phone") or billing.get("phone") or "",
            "order_items": items,
            "payment_method": payment_method,
            "shipping_charges": str(order.shipping_cost),
            "giftwrap_charges": "0",
            "transaction_charges": "0",
            "total_discount": str(order.discount_amount),
            "sub_total": str(order.subtotal),
            "length": length_default,
            "breadth": breadth_default,
            "height": height_default,
            "weight": weight_default,
        }

    def create_order(self, order) -> ProviderResponse:
        payload = self._build_order_payload(order)
        result = self._request(method="POST", path="/v1/external/orders/create/adhoc", payload=payload)
        if not result.success:
            return result

        data = result.data or {}
        shipment_id = (
            data.get("shipment_id")
            or (data.get("shipment_details") or {}).get("shipment_id")
            or ""
        )
        provider_order_id = data.get("order_id") or payload["order_id"]
        normalized = {
            "external_order_id": str(provider_order_id),
            "external_shipment_id": str(shipment_id),
            "raw": data,
        }
        return ProviderResponse(success=True, status=ShipmentStatus.CREATED, data=normalized)

    def assign_awb(self, shipment) -> ProviderResponse:
        if not shipment.external_shipment_id:
            return ProviderResponse(success=False, error_code="validation_error", error_message="Missing external shipment ID")

        payload = {
            "shipment_id": int(shipment.external_shipment_id),
            "pickup_id": int(self._settings().get("pickup_id") or 0),
        }
        result = self._request(method="POST", path="/v1/external/courier/assign/awb", payload=payload)
        if not result.success:
            return result

        data = result.data or {}
        awb = str(data.get("awb_code") or data.get("awb") or "")
        return ProviderResponse(
            success=True,
            status=ShipmentStatus.AWB_ASSIGNED,
            data={
                "awb_code": awb,
                "courier_name": data.get("courier_name") or "",
                "courier_company_id": str(data.get("courier_company_id") or ""),
                "raw": data,
            },
        )

    def generate_label(self, shipment) -> ProviderResponse:
        if not shipment.external_shipment_id:
            return ProviderResponse(success=False, error_code="validation_error", error_message="Missing external shipment ID")
        payload = {"shipment_id": [int(shipment.external_shipment_id)]}
        result = self._request(method="POST", path="/v1/external/courier/generate/label", payload=payload)
        if not result.success:
            return result
        data = result.data or {}
        return ProviderResponse(success=True, data={"label_url": data.get("label_url") or "", "raw": data})

    def generate_manifest(self, shipment) -> ProviderResponse:
        if not shipment.external_shipment_id:
            return ProviderResponse(success=False, error_code="validation_error", error_message="Missing external shipment ID")
        payload = {"shipment_id": [int(shipment.external_shipment_id)]}
        result = self._request(method="POST", path="/v1/external/manifests/generate", payload=payload)
        if not result.success:
            return result
        data = result.data or {}
        return ProviderResponse(success=True, data={"manifest_url": data.get("manifest_url") or "", "raw": data})

    def request_pickup(self, shipment) -> ProviderResponse:
        if not shipment.external_shipment_id:
            return ProviderResponse(success=False, error_code="validation_error", error_message="Missing external shipment ID")
        payload = {"shipment_id": [int(shipment.external_shipment_id)]}
        result = self._request(method="POST", path="/v1/external/courier/generate/pickup", payload=payload)
        if not result.success:
            return result
        data = result.data or {}
        return ProviderResponse(success=True, status=ShipmentStatus.PICKUP_REQUESTED, data={"raw": data})

    def cancel_shipment(self, shipment) -> ProviderResponse:
        if not shipment.external_order_id:
            return ProviderResponse(success=False, error_code="validation_error", error_message="Missing external order ID")
        payload = {"ids": [shipment.external_order_id]}
        result = self._request(method="POST", path="/v1/external/orders/cancel", payload=payload)
        if not result.success:
            return result
        return ProviderResponse(success=True, status=ShipmentStatus.CANCELLED, data={"raw": result.data or {}})

    def get_tracking(self, shipment) -> ProviderResponse:
        if not shipment.awb_code:
            return ProviderResponse(success=False, error_code="validation_error", error_message="Missing AWB code")

        params = {
            "awb": shipment.awb_code,
            "courier_company_id": shipment.courier_company_id or "",
        }
        result = self._request(method="GET", path="/v1/external/courier/track/awb", params=params)
        if not result.success:
            return result
        data = result.data or {}
        tracking_data = (data.get("tracking_data") or {}).get("shipment_track") or []
        latest = tracking_data[0] if tracking_data else {}
        internal_status = self.normalize_status(latest)
        return ProviderResponse(
            success=True,
            status=internal_status,
            data={
                "provider_status": latest.get("current_status") or "",
                "tracking_url": ((data.get("tracking_data") or {}).get("track_url") or ""),
                "event": latest,
                "raw": data,
            },
        )

    def verify_serviceability(self, order_or_address) -> ProviderResponse:
        address = order_or_address.shipping_address if hasattr(order_or_address, "shipping_address") else order_or_address
        params = {
            "pickup_postcode": self._settings().get("pickup_pincode") or "",
            "delivery_postcode": (address or {}).get("pincode") or "",
            "weight": str((self._provider_settings().get("default_package") or {}).get("weight_kg") or 0.3),
            "cod": 1 if str(getattr(order_or_address, "payment_method", "")).lower() == "cod" else 0,
        }
        result = self._request(method="GET", path="/v1/external/courier/serviceability/", params=params)
        if not result.success:
            return result
        return ProviderResponse(success=True, data={"raw": result.data or {}})

    def normalize_status(self, payload: dict[str, Any]) -> str:
        provider_status = str(
            payload.get("current_status")
            or payload.get("shipment_status")
            or payload.get("status")
            or ""
        ).strip().lower()
        return self.STATUS_MAP.get(provider_status, ShipmentStatus.IN_TRANSIT if provider_status else ShipmentStatus.CREATED)

    @classmethod
    def build_event_idempotency_key(cls, payload: dict[str, Any]) -> str:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return f"shiprocket:{hashlib.sha256(body.encode('utf-8')).hexdigest()}"
