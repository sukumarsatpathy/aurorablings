from __future__ import annotations

import base64
import hashlib
import hmac
import time
import json
from decimal import Decimal
from typing import Any

from django.conf import settings

from .base import (
    BasePaymentProvider,
    CheckoutOrderResult,
    PaymentResult,
    RefundResult,
    StatusResult,
    VerificationResult,
    WebhookResult,
    QRCodeResult,
)


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

    def _get_client(self):
        try:
            import razorpay
        except ImportError as exc:
            raise RuntimeError(
                "Razorpay SDK is not installed. Add 'razorpay' to backend requirements."
            ) from exc
        return razorpay.Client(auth=(self.key_id, self.key_secret))

    def create_checkout_order(
        self,
        *,
        order_id: str,
        amount: Decimal,
        currency: str,
        customer_email: str,
        customer_name: str,
        customer_phone: str = "",
        metadata: dict | None = None,
    ) -> CheckoutOrderResult:
        self._load_runtime_config()
        if not self.key_id or not self.key_secret:
            return CheckoutOrderResult(
                success=False,
                provider_ref="",
                amount=amount,
                currency=currency,
                error="Razorpay credentials missing. Set key_id and key_secret in payment settings.",
            )

        try:
            client = self._get_client()
            amount_paise = int(Decimal(str(amount or 0)) * 100)
            payload = {
                "amount": amount_paise,
                "currency": currency or "INR",
                "receipt": order_id,
                "notes": self.build_metadata(order_id, metadata),
            }
            data = client.order.create(data=payload)
            provider_ref = str(data.get("id") or "").strip()
            return CheckoutOrderResult(
                success=True,
                provider_ref=provider_ref,
                amount=Decimal(str(data.get("amount") or amount_paise)) / Decimal("100"),
                currency=str(data.get("currency") or currency or "INR").upper(),
                key_id=self.key_id,
                raw_response={**data, "key_id": self.key_id},
            )
        except Exception as exc:
            return CheckoutOrderResult(
                success=False,
                provider_ref="",
                amount=amount,
                currency=currency,
                error=str(exc),
            )

    def verify_payment_signature(
        self,
        *,
        provider_order_id: str,
        provider_payment_id: str,
        signature: str,
    ) -> VerificationResult:
        self._load_runtime_config()
        if not self.key_id or not self.key_secret:
            return VerificationResult(
                success=False,
                provider_ref=provider_payment_id,
                order_ref=provider_order_id,
                error="Razorpay credentials missing. Set key_id and key_secret in payment settings.",
            )

        try:
            client = self._get_client()
            client.utility.verify_payment_signature(
                {
                    "razorpay_order_id": provider_order_id,
                    "razorpay_payment_id": provider_payment_id,
                    "razorpay_signature": signature,
                }
            )
            return VerificationResult(
                success=True,
                provider_ref=provider_payment_id,
                order_ref=provider_order_id,
                raw_response={
                    "razorpay_order_id": provider_order_id,
                    "razorpay_payment_id": provider_payment_id,
                },
            )
        except Exception as exc:
            return VerificationResult(
                success=False,
                provider_ref=provider_payment_id,
                order_ref=provider_order_id,
                error=str(exc),
            )

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
            # On qr_code.credited the notes we set at creation live on the QR
            # entity, not on the payment, so fall back to it before giving up.
            qr_entity = (
                data.get("payload", {}).get("qr_code", {}).get("entity", {})
            )
            qr_notes = qr_entity.get("notes", {}) if isinstance(qr_entity, dict) else {}
            order_ref = str(
                (notes or {}).get("order_id")
                or (qr_notes or {}).get("order_id")
                or entity.get("order_id")
                or ""
            ).strip()
            provider_order_id = str(entity.get("order_id") or "").strip()
            provider_ref = str(entity.get("id") or "").strip()
            amount = Decimal(str((entity.get("amount") or 0))) / Decimal("100")
            currency = str(entity.get("currency") or "INR").upper()

            # qr_code.credited carries the same payment entity as payment.captured
            # and is what a counter QR actually fires. Treating it as pending here
            # would leave the customer paid and the counter waiting forever.
            if event in {"payment.captured", "qr_code.credited"}:
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
                raw_data={
                    **data,
                    "_provider_order_id": provider_order_id,
                },
            )
        except Exception as exc:
            return WebhookResult(
                verified=False, provider_ref="", order_ref="", status="failed",
                amount=Decimal("0"), currency="INR", error=str(exc),
            )

    def create_qr_code(
        self,
        *,
        order_id: str,
        amount: Decimal,
        currency: str = "INR",
        close_by_minutes: int = 15,
        metadata: dict | None = None,
    ) -> QRCodeResult:
        """
        A single-use, fixed-amount UPI QR for exactly one order.

        Every parameter here is load-bearing at a counter:
          usage=single_use   one QR, one collection — it cannot be paid twice
                             or rescued off a stall table tomorrow.
          fixed_amount       the customer cannot underpay or mistype, which is
                             the largest source of disputes with a static QR.
          close_by           the QR dies with the transaction.
          notes.order_id     what the webhook matches back to the order.
        """
        import requests

        self._load_runtime_config()
        if not self.key_id or not self.key_secret:
            return QRCodeResult(success=False, error="Razorpay credentials missing.")

        amount_paise = int(Decimal(str(amount or 0)) * 100)
        if amount_paise <= 0:
            return QRCodeResult(success=False, error="QR amount must be positive.")

        close_by = int(time.time()) + max(60, int(close_by_minutes) * 60)
        payload = {
            "type": "upi_qr",
            "name": "Aurora Blings",
            "usage": "single_use",
            "fixed_amount": True,
            "payment_amount": amount_paise,
            "description": f"Order {order_id}",
            "close_by": close_by,
            "notes": {"order_id": order_id, **(metadata or {})},
        }

        try:
            resp = requests.post(
                "https://api.razorpay.com/v1/payment/qr_codes",
                json=payload,
                auth=(self.key_id, self.key_secret),
                timeout=20,
            )
            body = resp.json() if resp.content else {}
        except Exception as exc:  # noqa: BLE001
            return QRCodeResult(success=False, error=f"Razorpay QR request failed: {exc}")

        if resp.status_code not in (200, 201):
            # A 400 here is usually "QR codes not enabled on this account" rather
            # than a bad request. The caller falls back to a payment link.
            message = (body.get("error", {}) or {}).get("description") or resp.text[:200]
            return QRCodeResult(success=False, error=f"Razorpay QR rejected ({resp.status_code}): {message}", raw=body)

        return QRCodeResult(
            success=True,
            provider_ref=str(body.get("id") or ""),
            image_url=str(body.get("image_url") or ""),
            amount=Decimal(str(body.get("payment_amount") or amount_paise)) / Decimal("100"),
            close_by=body.get("close_by"),
            raw=body,
        )

    def close_qr_code(self, *, provider_ref: str) -> bool:
        """Close a QR so a regenerated one cannot be paid alongside it."""
        import requests

        self._load_runtime_config()
        if not provider_ref:
            return False
        try:
            resp = requests.post(
                f"https://api.razorpay.com/v1/payment/qr_codes/{provider_ref}/close",
                auth=(self.key_id, self.key_secret),
                timeout=15,
            )
            return resp.status_code in (200, 201)
        except Exception:  # noqa: BLE001
            return False

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

            if str(provider_ref).startswith("order_"):
                resp = requests.get(
                    f"{self.base_url}/orders/{provider_ref}/payments",
                    headers={"Authorization": self._auth_header()},
                    timeout=15,
                )
                resp.raise_for_status()
                data = resp.json()
                items = data.get("items") if isinstance(data, dict) else []
                if not isinstance(items, list):
                    items = []

                latest = items[0] if items else {}
                status = "pending"
                payment_ref = provider_ref
                amount = None
                if latest:
                    payment_ref = str(latest.get("id") or provider_ref).strip()
                    amount = Decimal(str(latest.get("amount") or 0)) / Decimal("100")
                    status_raw = str(latest.get("status") or "").lower()
                    if status_raw == "captured":
                        status = "success"
                    elif status_raw == "failed":
                        status = "failed"
                return StatusResult(
                    success=True,
                    provider_ref=payment_ref,
                    status=status,
                    amount=amount,
                    raw_response=data if isinstance(data, dict) else {"items": items},
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
