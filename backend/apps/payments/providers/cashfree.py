"""
payments.providers.cashfree
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Cashfree Payments integration.

Docs: https://docs.cashfree.com/docs/pg-new-apis-endpoint

Environment variables required:
    CASHFREE_APP_ID        → API key ID
    CASHFREE_SECRET_KEY    → API secret
    CASHFREE_ENV           → "sandbox" | "production"

Webhook signature:
    Cashfree signs the payload with HMAC-SHA256 using the secret key.
    Header: x-webhook-signature  (base64-encoded)
    Header: x-webhook-timestamp
"""

from __future__ import annotations

import hashlib
import hmac
import base64
import json
from decimal import Decimal
from typing import Any

from django.conf import settings

from .base import BasePaymentProvider, PaymentResult, WebhookResult, RefundResult, StatusResult


class CashfreeProvider(BasePaymentProvider):
    name                 = "cashfree"
    display_name         = "Cashfree"
    supported_currencies = ["INR"]
    supports_refunds     = True
    supports_webhooks    = True

    def __init__(self):
        # Runtime config is loaded lazily per call so AppSetting changes can
        # take effect without service restarts.
        self.app_id = ""
        self.secret_key = ""
        self.webhook_secret = ""
        self.env = "sandbox"
        self.base_url = "https://sandbox.cashfree.com/pg"

    def _load_runtime_config(self) -> None:
        """
        Resolve credentials in this order:
        1) AppSetting (payment/cashfree keys)
        2) Active ProviderConfig under payment feature
        3) Django settings/env vars
        """
        app_id = str(getattr(settings, "CASHFREE_APP_ID", "") or "").strip()
        secret_key = str(getattr(settings, "CASHFREE_SECRET_KEY", "") or "").strip()
        webhook_secret = str(getattr(settings, "CASHFREE_WEBHOOK_SECRET", "") or "").strip()
        env = str(getattr(settings, "CASHFREE_ENV", "sandbox") or "sandbox").strip().lower()

        # Optional DB-based override via existing AppSetting config system.
        try:
            from apps.features.models import AppSetting, ProviderConfig

            config: dict[str, Any] = {}

            setting = (
                AppSetting.objects
                .filter(key__in=[
                    "payment.cashfree",
                    "payment-cashfree",
                    "payment_cashfree",
                    "cashfree",
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
                        provider_key="cashfree",
                        is_active=True,
                        feature__category="payment",
                    )
                    .select_related("feature")
                    .order_by("-updated_at")
                    .first()
                )
                if provider_row and isinstance(provider_row.config, dict):
                    config = provider_row.config

            if config:
                app_id = str(config.get("app_id") or config.get("client_id") or app_id).strip()
                secret_key = str(config.get("secret_key") or config.get("client_secret") or secret_key).strip()
                webhook_secret = str(config.get("webhook_secret") or webhook_secret).strip()
                env = str(config.get("environment") or config.get("env") or env).strip().lower()
        except Exception:
            # Keep env/settings fallback if DB/config table is unavailable.
            pass

        if env not in {"sandbox", "production"}:
            env = "sandbox"

        self.app_id = app_id
        self.secret_key = secret_key
        self.webhook_secret = webhook_secret
        self.env = env
        self.base_url = (
            "https://api.cashfree.com/pg"
            if env == "production"
            else "https://sandbox.cashfree.com/pg"
        )

    # ── Initiate ──────────────────────────────────────────────

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

        if not self.app_id or not self.secret_key:
            return PaymentResult(
                success=False,
                provider_ref="",
                error="Cashfree credentials missing. Set app_id and secret_key in payment settings.",
                raw_response={},
            )

        payload = {
            "order_id":      order_id,
            "order_amount":  float(amount),
            "order_currency": currency,
            "customer_details": {
                "customer_id":    order_id,
                "customer_email": customer_email,
                "customer_name":  customer_name,
                "customer_phone": customer_phone,
            },
            "order_meta": {
                "return_url": return_url or f"{settings.FRONTEND_URL}/orders/{order_id}",
            },
            **(metadata or {}),
        }

        try:
            resp = requests.post(
                f"{self.base_url}/orders",
                json=payload,
                headers=self._headers(),
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return PaymentResult(
                success=True,
                # Use merchant order_id as primary reference for status APIs.
                provider_ref=data.get("order_id", "") or data.get("cf_order_id", ""),
                payment_url=data.get("payment_session_id", ""),  # used in JS SDK
                raw_response=data,
            )
        except requests.HTTPError as exc:
            response = exc.response
            body = ""
            if response is not None:
                try:
                    parsed = response.json()
                    body = json.dumps(parsed)
                except Exception:
                    body = str(response.text or "")
            message = f"{exc}"
            if body:
                message = f"{message} | cashfree_response={body}"
            return PaymentResult(success=False, provider_ref="", error=message, raw_response={"error": body} if body else {})
        except Exception as exc:
            return PaymentResult(success=False, provider_ref="", error=str(exc))

    # ── Webhook ──────────────────────────────────────────────

    def verify_webhook(self, *, payload: bytes, headers: dict) -> WebhookResult:
        """
        Verify Cashfree webhook signature.

        Signature = base64( HMAC-SHA256( timestamp + payload, secret_key ) )
        """
        self._load_runtime_config()

        normalized_headers = {str(k).lower(): v for k, v in (headers or {}).items()}
        timestamp = normalized_headers.get("x-webhook-timestamp", "")
        signature = normalized_headers.get("x-webhook-signature", "")

        if not timestamp or not signature:
            return WebhookResult(verified=False, provider_ref="", order_ref="",
                                 status="failed", amount=Decimal(0), currency="INR",
                                 error="Missing signature headers.")

        message  = timestamp.encode() + payload
        signing_secret = self.webhook_secret or self.secret_key
        expected = base64.b64encode(
            hmac.new(
                signing_secret.encode(),
                message,
                hashlib.sha256,
            ).digest()
        ).decode()

        if not hmac.compare_digest(expected, signature):
            return WebhookResult(verified=False, provider_ref="", order_ref="",
                                 status="failed", amount=Decimal(0), currency="INR",
                                 error="Invalid signature.")

        try:
            data       = json.loads(payload)
            nested = data.get("data", {}) if isinstance(data, dict) else {}
            if not isinstance(nested, dict):
                nested = {}

            refund = nested.get("refund")
            if isinstance(refund, dict):
                refund_status_map = {
                    "SUCCESS": "success",
                    "PROCESSED": "success",
                    "FAILED": "failed",
                    "CANCELLED": "failed",
                    "PENDING": "pending",
                }
                return WebhookResult(
                    verified=True,
                    provider_ref=str(refund.get("cf_payment_id") or refund.get("payment_id") or "").strip(),
                    order_ref=str(refund.get("order_id") or "").strip(),
                    status=refund_status_map.get(str(refund.get("refund_status") or "").upper(), "pending"),
                    amount=Decimal(str(refund.get("refund_amount", 0))),
                    currency=str(refund.get("refund_currency") or "INR"),
                    raw_data=data,
                )

            order_data = nested.get("order", {}) if isinstance(nested.get("order"), dict) else {}
            payment    = nested.get("payment", {}) if isinstance(nested.get("payment"), dict) else {}
            status_map = {
                "SUCCESS": "success",
                "FAILED":  "failed",
                "PENDING": "pending",
            }
            return WebhookResult(
                verified=True,
                provider_ref=str(payment.get("cf_payment_id") or "").strip(),
                order_ref=str(order_data.get("order_id") or "").strip(),
                status=status_map.get(str(payment.get("payment_status") or "").upper(), "pending"),
                amount=Decimal(str(payment.get("payment_amount", 0))),
                currency=str(payment.get("payment_currency") or "INR"),
                raw_data=data,
            )
        except Exception as exc:
            return WebhookResult(verified=True, provider_ref="", order_ref="",
                                 status="failed", amount=Decimal(0), currency="INR",
                                 error=str(exc))

    # ── Refund ────────────────────────────────────────────────

    def refund(self, *, provider_ref: str, amount: Decimal, reason: str = "") -> RefundResult:
        import requests
        self._load_runtime_config()
        try:
            resp = requests.post(
                f"{self.base_url}/orders/{provider_ref}/refunds",
                json={"refund_amount": float(amount), "refund_note": reason},
                headers=self._headers(),
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return RefundResult(
                success=True,
                refund_ref=data.get("cf_refund_id", ""),
                amount=amount,
                raw_response=data,
            )
        except Exception as exc:
            return RefundResult(success=False, refund_ref="", amount=amount, error=str(exc))

    # ── Status ────────────────────────────────────────────────

    def get_status(self, *, provider_ref: str) -> StatusResult:
        import requests
        self._load_runtime_config()
        try:
            resp = requests.get(
                f"{self.base_url}/orders/{provider_ref}",
                headers=self._headers(),
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

            order_status = str(data.get("order_status") or "").upper()
            status_map = {
                "PAID": "success",
                "SUCCESS": "success",
                "ACTIVE": "pending",
                "PENDING": "pending",
                "EXPIRED": "failed",
                "CANCELLED": "failed",
                "FAILED": "failed",
            }
            normalized_status = status_map.get(order_status, "pending")

            # Cashfree can keep order_status=ACTIVE even when a payment is completed.
            # Check payment-level statuses to avoid false pending states.
            try:
                payments_resp = requests.get(
                    f"{self.base_url}/orders/{provider_ref}/payments",
                    headers=self._headers(),
                    timeout=15,
                )
                payments_resp.raise_for_status()
                payments_data = payments_resp.json()
                payments_rows = []
                if isinstance(payments_data, list):
                    payments_rows = payments_data
                elif isinstance(payments_data, dict):
                    raw_rows = payments_data.get("payments") or payments_data.get("data") or []
                    if isinstance(raw_rows, list):
                        payments_rows = raw_rows

                payment_statuses = {
                    str(row.get("payment_status") or row.get("status") or "").upper()
                    for row in payments_rows
                    if isinstance(row, dict)
                }
                if "SUCCESS" in payment_statuses:
                    normalized_status = "success"
                elif payment_statuses.intersection({"FAILED", "CANCELLED", "USER_DROPPED"}):
                    normalized_status = "failed"

                if isinstance(data, dict):
                    data["payments"] = payments_rows
            except Exception:
                # Keep order-level status as fallback when payment list API fails.
                pass

            return StatusResult(
                success=True,
                provider_ref=provider_ref,
                status=normalized_status,
                amount=Decimal(str(data.get("order_amount", 0))),
                raw_response=data,
            )
        except Exception as exc:
            return StatusResult(success=False, provider_ref=provider_ref, status="failed", error=str(exc))

    # ── Private ───────────────────────────────────────────────

    def _headers(self) -> dict:
        return {
            "Content-Type":  "application/json",
            "x-api-version": "2023-08-01",
            "x-client-id":   self.app_id,
            "x-client-secret": self.secret_key,
        }
