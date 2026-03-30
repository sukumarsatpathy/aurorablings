from __future__ import annotations

import base64
import hashlib
import hmac
import json
from decimal import Decimal
from typing import Any

from django.conf import settings

from .base import BasePaymentProvider, PaymentResult, WebhookResult, RefundResult, StatusResult


class RazorpayProvider(BasePaymentProvider):
    name = "razorpay"
    display_name = "Razorpay"
    supported_currencies = ["INR"]
    supports_refunds = True
    supports_webhooks = True

    def __init__(self):
        self.key_id = ""
        self.key_secret = ""
        self.webhook_secret = ""
        self.base_url = "https://api.razorpay.com/v1"

    def _load_runtime_config(self) -> None:
        key_id = str(getattr(settings, "RAZORPAY_KEY_ID", "") or "").strip()
        key_secret = str(getattr(settings, "RAZORPAY_KEY_SECRET", "") or "").strip()
        webhook_secret = str(getattr(settings, "RAZORPAY_WEBHOOK_SECRET", "") or "").strip()

        try:
            from apps.features.models import AppSetting, ProviderConfig

            config: dict[str, Any] = {}
            setting = (
                AppSetting.objects
                .filter(key__in=[
                    "payment.razorpay",
                    "payment-razorpay",
                    "payment_razorpay",
                    "razorpay",
                ])
                .order_by("-updated_at")
                .first()
            )
            if setting:
                value = setting.typed_value
                if isinstance(value, dict):
                    config = value
                elif isinstance(value, str):
                    try:
                        parsed = json.loads(value)
                        if isinstance(parsed, dict):
                            config = parsed
                    except Exception:
                        config = {}

            if not config:
                provider_row = (
                    ProviderConfig.objects
                    .filter(
                        provider_key="razorpay",
                        is_active=True,
                        feature__category="payment",
                    )
                    .order_by("-updated_at")
                    .first()
                )
                if provider_row and isinstance(provider_row.config, dict):
                    config = provider_row.config

            if config:
                key_id = str(config.get("key_id") or config.get("app_id") or key_id).strip()
                key_secret = str(config.get("key_secret") or config.get("secret_key") or key_secret).strip()
                webhook_secret = str(config.get("webhook_secret") or webhook_secret).strip()
        except Exception:
            pass

        self.key_id = key_id
        self.key_secret = key_secret
        self.webhook_secret = webhook_secret

    def _auth_header(self) -> str:
        token = base64.b64encode(f"{self.key_id}:{self.key_secret}".encode("utf-8")).decode("utf-8")
        return f"Basic {token}"

    def initiate(
        self,
        *,
        order_id: str,
        amount: Decimal,
        currency: str = "INR",
        customer_email: str,
        customer_name: str,
        customer_phone: str = "",
        return_url: str = "",
        metadata: dict | None = None,
    ) -> PaymentResult:
        import requests

        self._load_runtime_config()
        if not self.key_id or not self.key_secret:
            return PaymentResult(
                success=False,
                provider_ref="",
                error="Razorpay credentials missing. Set key_id and key_secret in payment settings.",
            )

        amount_paise = int(Decimal(str(amount or 0)) * 100)
        payload = {
            "amount": amount_paise,
            "currency": currency or "INR",
            "accept_partial": False,
            "reference_id": order_id,
            "description": f"Aurora Blings Order {order_id}",
            "customer": {
                "name": customer_name or "Customer",
                "email": customer_email or "",
                "contact": customer_phone or "",
            },
            "notify": {"sms": bool(customer_phone), "email": bool(customer_email)},
            "reminder_enable": True,
            "notes": {"order_id": order_id, **(metadata or {})},
        }
        if return_url:
            payload["callback_url"] = return_url
            payload["callback_method"] = "get"

        try:
            resp = requests.post(
                f"{self.base_url}/payment_links",
                json=payload,
                headers={
                    "Authorization": self._auth_header(),
                    "Content-Type": "application/json",
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return PaymentResult(
                success=True,
                provider_ref=str(data.get("id") or "").strip(),  # plink_xxx
                payment_url=str(data.get("short_url") or data.get("url") or "").strip(),
                raw_response=data,
            )
        except requests.HTTPError as exc:
            body = ""
            if exc.response is not None:
                try:
                    body = json.dumps(exc.response.json())
                except Exception:
                    body = str(exc.response.text or "")
            err = f"{exc}"
            if body:
                err = f"{err} | razorpay_response={body}"
            return PaymentResult(success=False, provider_ref="", error=err, raw_response={"error": body} if body else {})
        except Exception as exc:
            return PaymentResult(success=False, provider_ref="", error=str(exc))

    def verify_webhook(self, *, payload: bytes, headers: dict) -> WebhookResult:
        self._load_runtime_config()
        signature = str((headers or {}).get("x-razorpay-signature", "") or "").strip()
        if not signature:
            return WebhookResult(
                verified=False, provider_ref="", order_ref="", status="failed",
                amount=Decimal("0"), currency="INR", error="Missing x-razorpay-signature header.",
            )
        if not self.webhook_secret:
            return WebhookResult(
                verified=False, provider_ref="", order_ref="", status="failed",
                amount=Decimal("0"), currency="INR", error="Razorpay webhook secret not configured.",
            )

        expected = hmac.new(
            self.webhook_secret.encode("utf-8"),
            payload or b"",
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, signature):
            return WebhookResult(
                verified=False, provider_ref="", order_ref="", status="failed",
                amount=Decimal("0"), currency="INR", error="Invalid webhook signature.",
            )

        try:
            data = json.loads(payload or b"{}")
            event = str(data.get("event") or "").strip().lower()
            entity = (
                data.get("payload", {})
                .get("payment", {})
                .get("entity", {})
            )
            notes = entity.get("notes", {}) if isinstance(entity, dict) else {}
            order_ref = str(
                (notes or {}).get("order_id")
                or entity.get("order_id")
                or ""
            ).strip()
            provider_ref = str(entity.get("id") or "").strip()
            amount = Decimal(str((entity.get("amount") or 0))) / Decimal("100")
            currency = str(entity.get("currency") or "INR").upper()

            if event == "payment.captured":
                status = "success"
            elif event in {"payment.failed"}:
                status = "failed"
            else:
                status = "pending"

            return WebhookResult(
                verified=True,
                provider_ref=provider_ref,
                order_ref=order_ref,
                status=status,
                amount=amount,
                currency=currency,
                raw_data=data,
            )
        except Exception as exc:
            return WebhookResult(
                verified=False, provider_ref="", order_ref="", status="failed",
                amount=Decimal("0"), currency="INR", error=str(exc),
            )

    def refund(self, *, provider_ref: str, amount: Decimal, reason: str = "") -> RefundResult:
        import requests

        self._load_runtime_config()
        if not provider_ref.startswith("pay_"):
            return RefundResult(
                success=False,
                refund_ref="",
                amount=amount,
                error="Refund requires Razorpay payment id (pay_*).",
            )
        try:
            resp = requests.post(
                f"{self.base_url}/payments/{provider_ref}/refund",
                json={"amount": int(Decimal(str(amount)) * 100), "notes": {"reason": reason or ""}},
                headers={"Authorization": self._auth_header(), "Content-Type": "application/json"},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return RefundResult(
                success=True,
                refund_ref=str(data.get("id") or "").strip(),
                amount=amount,
                raw_response=data,
            )
        except Exception as exc:
            return RefundResult(success=False, refund_ref="", amount=amount, error=str(exc))

    def get_status(self, *, provider_ref: str) -> StatusResult:
        import requests

        self._load_runtime_config()
        try:
            if str(provider_ref).startswith("plink_"):
                resp = requests.get(
                    f"{self.base_url}/payment_links/{provider_ref}",
                    headers={"Authorization": self._auth_header()},
                    timeout=15,
                )
                resp.raise_for_status()
                data = resp.json()
                status_raw = str(data.get("status") or "").lower()
                status_map = {"paid": "success", "cancelled": "failed", "expired": "failed"}
                status = status_map.get(status_raw, "pending")
                amount = Decimal(str(data.get("amount") or 0)) / Decimal("100")
                return StatusResult(
                    success=True,
                    provider_ref=provider_ref,
                    status=status,
                    amount=amount,
                    raw_response=data,
                )

            resp = requests.get(
                f"{self.base_url}/payments/{provider_ref}",
                headers={"Authorization": self._auth_header()},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            status_raw = str(data.get("status") or "").lower()
            status_map = {"captured": "success", "failed": "failed", "authorized": "pending", "created": "pending"}
            return StatusResult(
                success=True,
                provider_ref=provider_ref,
                status=status_map.get(status_raw, "pending"),
                amount=Decimal(str(data.get("amount") or 0)) / Decimal("100"),
                raw_response=data,
            )
        except Exception as exc:
            return StatusResult(success=False, provider_ref=provider_ref, status="failed", error=str(exc))
