"""
NimbusPost courier aggregator — https://nimbuspost.com

Written against NimbusPost's published API (Postman collection 9692837/TW6wHnoz,
https://documenter.getpostman.com/view/9692837/TW6wHnoz):

    POST /users/login                 {email, password}       → data: JWT (≈3 h)
    POST /courier/serviceability      {origin, destination, payment_type, …}
                                                              → data: [couriers + charges]
    POST /shipments                   order + consignee + pickup → awb, courier, label
    GET  /shipments/track/{awb}       → status + history
    POST /shipments/cancel            {awb}
    POST /shipments/manifest          {awbs: [...]}            → data: manifest PDF url

Every call after login sends `Authorization: Bearer <token>`.

Credentials: NIMBUSPOST_EMAIL / NIMBUSPOST_PASSWORD environment variables (the
password is deliberately not stored in the admin-editable AppSetting, which staff
can read). Everything else — pickup address, warehouse name, preferred courier —
lives in the `shipping.nimbuspost` app setting.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from apps.features import services as feature_services
from apps.shipping.models import ShipmentStatus
from core.logging import get_logger

from .base import BaseShippingProvider, ProviderResponse

logger = get_logger(__name__)

TOKEN_CACHE_KEY = "nimbuspost:auth_token:v1"
TOKEN_TTL_SECONDS = int(2.5 * 3600)  # NimbusPost tokens live ~3 h
DEFAULT_BASE_URL = "https://api.nimbuspost.com/v1"

#: Courier fields that may carry a delivery estimate. NimbusPost's docs don't
#: list one, but the serviceability response is read defensively so dates are
#: used automatically if the account's response includes them.
EDD_DAY_KEYS = ("estimated_delivery_days", "expected_delivery_days", "delivery_days", "edd_days", "tat", "transit_days")
EDD_DATE_KEYS = ("edd", "estimated_delivery_date", "expected_delivery_date", "etd")


def _digits(value: Any) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def _phone10(value: Any) -> str:
    """NimbusPost wants a 10-digit mobile; drop +91 / leading 0."""
    digits = _digits(value)
    return digits[-10:] if len(digits) >= 10 else digits


def _parse_days(courier: dict[str, Any], *, today: date) -> int | None:
    for key in EDD_DAY_KEYS:
        raw = courier.get(key)
        if raw in (None, ""):
            continue
        try:
            days = int(float(str(raw).split("-")[0].strip()))
        except ValueError:
            continue
        if days > 0:
            return days
    for key in EDD_DATE_KEYS:
        raw = str(courier.get(key) or "").strip()
        if not raw:
            continue
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%b %d, %Y", "%d %b %Y", "%Y-%m-%d %H:%M:%S"):
            try:
                days = (datetime.strptime(raw, fmt).date() - today).days
            except ValueError:
                continue
            if days > 0:
                return days
            break
    return None


class NimbusPostProvider(BaseShippingProvider):
    name = "nimbuspost"

    # Text statuses (webhooks / shipment "status") and the short codes used in
    # tracking history (PP, IT, EX, OFD, DL, RT, RT-IT, RT-DL).
    STATUS_MAP = {
        "pending": ShipmentStatus.PENDING_APPROVAL,
        "approved": ShipmentStatus.APPROVED,
        "booked": ShipmentStatus.BOOKED,
        "manifested": ShipmentStatus.BOOKED,
        "pp": ShipmentStatus.PICKUP_REQUESTED,
        "pending_pickup": ShipmentStatus.PICKUP_REQUESTED,
        "picked": ShipmentStatus.PICKED_UP,
        "picked_up": ShipmentStatus.PICKED_UP,
        "it": ShipmentStatus.IN_TRANSIT,
        "in_transit": ShipmentStatus.IN_TRANSIT,
        "ofd": ShipmentStatus.OUT_FOR_DELIVERY,
        "out_for_delivery": ShipmentStatus.OUT_FOR_DELIVERY,
        "dl": ShipmentStatus.DELIVERED,
        "delivered": ShipmentStatus.DELIVERED,
        "ex": ShipmentStatus.EXCEPTION,
        "exception": ShipmentStatus.EXCEPTION,
        "failed": ShipmentStatus.FAILED,
        "cancelled": ShipmentStatus.CANCELLED,
        "canceled": ShipmentStatus.CANCELLED,
        "rt": ShipmentStatus.RTO,
        "rt-it": ShipmentStatus.RTO,
        "rto": ShipmentStatus.RTO,
        "rt-dl": ShipmentStatus.RETURNED,
        "returned": ShipmentStatus.RETURNED,
    }

    # ── Configuration ─────────────────────────────────────────

    def _cfg(self) -> dict[str, Any]:
        cfg = feature_services.get_setting("shipping.nimbuspost", default={}) or {}
        return cfg if isinstance(cfg, dict) else {}

    def _provider_cfg(self) -> dict[str, Any]:
        cfg = feature_services.get_setting("shipping.provider", default={}) or {}
        return cfg if isinstance(cfg, dict) else {}

    def _base_url(self) -> str:
        url = str(self._cfg().get("base_url") or getattr(settings, "NIMBUSPOST_BASE_URL", "") or DEFAULT_BASE_URL)
        return url.rstrip("/")

    def _credentials(self) -> tuple[str, str]:
        email = str(getattr(settings, "NIMBUSPOST_EMAIL", "") or self._cfg().get("email") or "").strip()
        password = str(getattr(settings, "NIMBUSPOST_PASSWORD", "") or "").strip()
        return email, password

    def _timeout(self) -> float:
        try:
            return float(self._cfg().get("timeout_seconds") or getattr(settings, "NIMBUSPOST_TIMEOUT_SECONDS", 20))
        except (TypeError, ValueError):
            return 20.0

    def is_configured(self) -> bool:
        email, password = self._credentials()
        return bool(email and password)

    def pickup_pincode(self) -> str:
        return _digits(self._cfg().get("pickup_pincode"))[:6]

    def _package(self) -> dict[str, int]:
        pkg = self._provider_cfg().get("default_package") or {}
        try:
            return {
                "weight": max(1, int(float(pkg.get("weight_kg") or 0.3) * 1000)),
                "length": max(1, int(float(pkg.get("length_cm") or 12))),
                "breadth": max(1, int(float(pkg.get("breadth_cm") or 12))),
                "height": max(1, int(float(pkg.get("height_cm") or 4))),
            }
        except (TypeError, ValueError):
            return {"weight": 300, "length": 12, "breadth": 12, "height": 4}

    # ── Auth ──────────────────────────────────────────────────

    def authenticate(self, *, force: bool = False) -> ProviderResponse:
        if not force:
            token = cache.get(TOKEN_CACHE_KEY)
            if token:
                return ProviderResponse(success=True, data={"token": token})

        email, password = self._credentials()
        if not (email and password):
            return ProviderResponse(
                success=False, error_code="config_error",
                error_message="NimbusPost login not configured (set NIMBUSPOST_EMAIL and NIMBUSPOST_PASSWORD).",
            )
        try:
            response = requests.post(
                f"{self._base_url()}/users/login",
                json={"email": email, "password": password},
                headers={"Content-Type": "application/json"},
                timeout=self._timeout(),
            )
            body = response.json() if response.content else {}
        except (requests.RequestException, ValueError) as exc:
            logger.warning("nimbuspost_login_failed", error=str(exc))
            return ProviderResponse(success=False, error_code="provider_temporary_failure", error_message=str(exc))

        token = body.get("data") if isinstance(body, dict) else None
        if not (isinstance(body, dict) and body.get("status") and isinstance(token, str) and token):
            message = str((body or {}).get("message") or f"Login failed (HTTP {response.status_code}).")
            logger.warning("nimbuspost_login_rejected", message=message)
            return ProviderResponse(success=False, error_code="auth_failed", error_message=message)

        cache.set(TOKEN_CACHE_KEY, token, timeout=TOKEN_TTL_SECONDS)
        return ProviderResponse(success=True, data={"token": token})

    def refresh_token(self) -> ProviderResponse:
        cache.delete(TOKEN_CACHE_KEY)
        return self.authenticate(force=True)

    def _request(
        self,
        *,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        timeout: float | None = None,
        retry_on_auth: bool = True,
    ) -> ProviderResponse:
        """
        Call NimbusPost. success=True only when HTTP is OK *and* the body says
        `"status": true`; otherwise the body's message is returned as the error.
        data always holds the parsed body (plus http_status).
        """
        auth = self.authenticate()
        if not auth.success:
            return auth

        try:
            response = requests.request(
                method=method,
                url=f"{self._base_url()}{path}",
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {auth.data['token']}"},
                json=payload,
                params=params,
                timeout=timeout or self._timeout(),
            )
        except requests.RequestException as exc:
            logger.warning("nimbuspost_request_failed", method=method, path=path, error=str(exc))
            return ProviderResponse(success=False, error_code="provider_temporary_failure", error_message=str(exc))

        try:
            body = response.json() if response.content else {}
        except ValueError:
            body = {}
        if not isinstance(body, dict):
            body = {"data": body}
        body.setdefault("http_status", response.status_code)

        message = str(body.get("message") or "")
        if retry_on_auth and (response.status_code == 401 or "token" in message.lower()):
            self.refresh_token()
            return self._request(method=method, path=path, payload=payload, params=params,
                                 timeout=timeout, retry_on_auth=False)

        if response.status_code >= 500:
            return ProviderResponse(success=False, error_code="provider_temporary_failure",
                                    error_message=message or f"HTTP {response.status_code}", data=body)
        if response.status_code >= 400 or not body.get("status"):
            return ProviderResponse(success=False, error_code="provider_rejected",
                                    error_message=message or f"HTTP {response.status_code}", data=body)
        return ProviderResponse(success=True, data=body)

    # ── Serviceability / delivery estimate ────────────────────

    def check_serviceability(
        self,
        *,
        destination: str,
        payment_type: str = "prepaid",
        order_amount: Decimal | float | int = 0,
        weight_grams: int | None = None,
        timeout: float | None = None,
    ) -> ProviderResponse:
        """
        Couriers that can carry a parcel from our pickup pincode to `destination`.

        data = {"serviceable": bool, "days": int | None, "couriers": [...], "raw": body}
        `days` is the quickest courier's estimate *if* NimbusPost includes one.
        """
        origin = self.pickup_pincode()
        if not origin:
            return ProviderResponse(success=False, error_code="config_error",
                                    error_message="NimbusPost pickup_pincode is not set in shipping.nimbuspost.")
        pkg = self._package()
        payload = {
            "origin": origin,
            "destination": _digits(destination)[:6],
            "payment_type": "cod" if payment_type == "cod" else "prepaid",
            "order_amount": str(order_amount or 0),
            "weight": str(weight_grams or pkg["weight"]),
            "length": str(pkg["length"]),
            "breadth": str(pkg["breadth"]),
            "height": str(pkg["height"]),
        }
        result = self._request(method="POST", path="/courier/serviceability", payload=payload, timeout=timeout)
        body = result.data or {}

        if not result.success:
            # A clear "no courier" answer is a real result, not an outage.
            if result.error_code == "provider_rejected" and "serv" in result.error_message.lower():
                return ProviderResponse(success=True, data={"serviceable": False, "days": None, "couriers": [], "raw": body})
            return result

        rows = body.get("data") if isinstance(body.get("data"), list) else []
        today = timezone.localdate()
        couriers = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            couriers.append({
                "id": str(row.get("id") or ""),
                "name": str(row.get("name") or ""),
                "total_charges": row.get("total_charges"),
                "days": _parse_days(row, today=today),
            })
        known_days = [c["days"] for c in couriers if c["days"]]
        return ProviderResponse(success=True, data={
            "serviceable": bool(couriers),
            "days": min(known_days) if known_days else None,
            "couriers": couriers,
            "raw": body,
        })

    def verify_serviceability(self, order_or_address) -> ProviderResponse:
        is_order = hasattr(order_or_address, "shipping_address")
        address = order_or_address.shipping_address if is_order else (order_or_address or {})
        pincode = _digits((address or {}).get("pincode"))
        if len(pincode) != 6:
            return ProviderResponse(success=False, error_code="validation_error", error_message="Missing destination pincode")
        result = self.check_serviceability(
            destination=pincode,
            payment_type=str(getattr(order_or_address, "payment_method", "") or "prepaid").lower(),
            order_amount=getattr(order_or_address, "grand_total", 0) or 0,
        )
        if result.success and not result.data.get("serviceable"):
            return ProviderResponse(success=False, error_code="not_serviceable",
                                    error_message=f"No NimbusPost courier delivers to {pincode}.", data=result.data)
        return result

    # ── Shipments ─────────────────────────────────────────────

    @staticmethod
    def _order_number(order) -> str:
        """NimbusPost caps order_number at 20 chars; ours are UUIDs."""
        return str(order.order_number or order.id).replace("-", "")[:20]

    def _pickup_block(self) -> dict[str, Any]:
        cfg = self._cfg()
        return {
            "warehouse_name": str(cfg.get("warehouse_name") or "")[:20],
            "name": str(cfg.get("pickup_name") or ""),
            "address": str(cfg.get("pickup_address") or ""),
            "address_2": str(cfg.get("pickup_address_2") or ""),
            "city": str(cfg.get("pickup_city") or ""),
            "state": str(cfg.get("pickup_state") or ""),
            "pincode": self.pickup_pincode(),
            "phone": _phone10(cfg.get("pickup_phone")),
        }

    def _build_order_payload(self, order) -> dict[str, Any]:
        shipping = order.shipping_address or {}
        items = list(order.items.all())
        pkg = self._package()
        snapshot_weight = sum(
            int((item.product_snapshot or {}).get("weight_grams") or 0) * int(item.quantity or 1) for item in items
        )
        is_cod = str(order.payment_method or "").lower() == "cod"
        payload: dict[str, Any] = {
            "order_number": self._order_number(order),
            "payment_type": "cod" if is_cod else "prepaid",
            "order_amount": float(order.grand_total or 0),
            "shipping_charges": float(order.shipping_cost or 0),
            "discount": float(order.discount_amount or 0),
            "cod_charges": 0,
            "package_weight": snapshot_weight or pkg["weight"],
            "package_length": pkg["length"],
            "package_breadth": pkg["breadth"],
            "package_height": pkg["height"],
            "request_auto_pickup": "yes" if self._provider_cfg().get("auto_request_pickup") else "no",
            "consignee": {
                "name": shipping.get("full_name") or "Customer",
                "address": shipping.get("line1") or "",
                "address_2": shipping.get("line2") or "",
                "city": shipping.get("city") or "",
                "state": shipping.get("state") or "",
                "pincode": _digits(shipping.get("pincode"))[:6],
                "phone": _phone10(shipping.get("phone")),
            },
            "pickup": self._pickup_block(),
            "order_items": [
                {
                    "name": item.product_name,
                    "qty": str(int(item.quantity)),
                    "price": str(item.unit_price),
                    "sku": item.sku,
                }
                for item in items
            ],
            "is_insurance": "0",
        }
        courier_id = str(self._cfg().get("courier_id") or "").strip()
        if courier_id:
            payload["courier_id"] = courier_id
        return payload

    def create_order(self, order) -> ProviderResponse:
        result = self._request(method="POST", path="/shipments", payload=self._build_order_payload(order))
        if not result.success:
            return result
        body = result.data or {}
        data = body.get("data") if isinstance(body.get("data"), dict) else {}
        awb = str(data.get("awb_number") or "")
        return ProviderResponse(
            success=True,
            status=ShipmentStatus.AWB_ASSIGNED if awb else ShipmentStatus.BOOKED,
            data={
                "external_order_id": str(data.get("order_id") or self._order_number(order)),
                "external_shipment_id": str(data.get("shipment_id") or ""),
                "awb_code": awb,
                "courier_name": str(data.get("courier_name") or ""),
                "courier_company_id": str(data.get("courier_id") or ""),
                "tracking_url": "",
                "label_url": str(data.get("label") or ""),
                "raw": body,
            },
        )

    def assign_awb(self, shipment) -> ProviderResponse:
        # NimbusPost returns the AWB at booking; nothing more to ask for.
        awb = str(shipment.awb_code or "")
        return ProviderResponse(
            success=bool(awb),
            status=ShipmentStatus.AWB_ASSIGNED if awb else ShipmentStatus.BOOKED,
            error_code="" if awb else "awb_missing",
            error_message="" if awb else "NimbusPost did not return an AWB at booking.",
            data={"awb_code": awb, "courier_name": shipment.courier_name or "",
                  "courier_company_id": shipment.courier_company_id or "", "raw": {}},
        )

    def generate_label(self, shipment) -> ProviderResponse:
        # The label PDF comes back with the booking; there is no separate label API.
        return ProviderResponse(success=bool(shipment.label_url), data={"label_url": shipment.label_url or "", "raw": {}})

    def generate_manifest(self, shipment) -> ProviderResponse:
        if shipment.manifest_url:
            return ProviderResponse(success=True, data={"manifest_url": shipment.manifest_url, "raw": {}})
        if not shipment.awb_code:
            return ProviderResponse(success=False, error_code="validation_error", error_message="Missing AWB")
        result = self._request(method="POST", path="/shipments/manifest", payload={"awbs": [shipment.awb_code]})
        if not result.success:
            return result
        url = (result.data or {}).get("data")
        return ProviderResponse(success=True, data={"manifest_url": str(url or ""), "raw": result.data})

    def request_pickup(self, shipment) -> ProviderResponse:
        # NimbusPost has no separate pickup call: pickup is requested at booking
        # (request_auto_pickup) or from the NimbusPost panel.
        if self._provider_cfg().get("auto_request_pickup"):
            return ProviderResponse(success=True, status=ShipmentStatus.PICKUP_REQUESTED,
                                    data={"raw": {"note": "Requested at booking (request_auto_pickup=yes)."}})
        return ProviderResponse(success=False, error_code="not_supported",
                                error_message="Request the pickup from the NimbusPost panel, or turn on Auto Request Pickup.")

    def cancel_shipment(self, shipment) -> ProviderResponse:
        if not shipment.awb_code:
            return ProviderResponse(success=False, error_code="validation_error", error_message="Missing AWB")
        result = self._request(method="POST", path="/shipments/cancel", payload={"awb": shipment.awb_code})
        if not result.success:
            return result
        return ProviderResponse(success=True, status=ShipmentStatus.CANCELLED, data={"raw": result.data or {}})

    def get_tracking(self, shipment) -> ProviderResponse:
        if not shipment.awb_code:
            return ProviderResponse(success=False, error_code="validation_error", error_message="Missing AWB")
        result = self._request(method="GET", path=f"/shipments/track/{shipment.awb_code}")
        if not result.success:
            return result
        body = result.data or {}
        track = body.get("data") if isinstance(body.get("data"), dict) else {}
        history = track.get("history") if isinstance(track.get("history"), list) else []
        latest = history[-1] if history and isinstance(history[-1], dict) else {}
        # An RTO shipment reports status "rto" with its own rto_status.
        status_payload = {"status": track.get("status")}
        if str(track.get("status") or "").lower() == "rto" and str(track.get("rto_status") or "").lower() == "delivered":
            status_payload = {"status": "returned"}
        elif latest.get("status_code") and not track.get("status"):
            status_payload = {"status": latest.get("status_code")}
        return ProviderResponse(
            success=True,
            status=self.normalize_status(status_payload),
            data={
                "provider_status": str(track.get("status") or latest.get("status_code") or ""),
                "tracking_url": "",
                "event": latest or track,
                "raw": body,
            },
        )

    def normalize_status(self, payload: dict[str, Any]) -> str:
        status = str(
            payload.get("status") or payload.get("current_status") or payload.get("shipment_status")
            or payload.get("status_code") or ""
        ).strip().lower()
        normalized = status.replace(" ", "_")
        mapped = self.STATUS_MAP.get(normalized) or self.STATUS_MAP.get(status)
        return mapped or (ShipmentStatus.IN_TRANSIT if normalized else ShipmentStatus.BOOKED)

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
