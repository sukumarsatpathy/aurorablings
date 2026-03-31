"""
payments.providers.phonepe
~~~~~~~~~~~~~~~~~~~~~~~~~~~
PhonePe Payment Gateway integration.

Docs: https://developer.phonepe.com/v1/reference/pay-api

Environment variables:
    PHONEPE_MERCHANT_ID   → Merchant ID
    PHONEPE_SALT_KEY      → Salt key for signature
    PHONEPE_SALT_INDEX    → Salt index (usually 1)
    PHONEPE_ENV           → "sandbox" | "production"

Webhook signature:
    X-VERIFY header = SHA256(base64(payload) + "/pg/v1/pay" + salt_key) + "###" + salt_index
"""

from __future__ import annotations

import base64
import hashlib
import hmac as _hmac
import json
from decimal import Decimal
from typing import Any

from django.conf import settings

from .base import BasePaymentProvider, PaymentResult, WebhookResult, RefundResult, StatusResult


class PhonePeProvider(BasePaymentProvider):
    name                 = "phonepe"
    display_name         = "PhonePe"
    supported_currencies = ["INR"]
    supports_refunds     = True
    supports_webhooks    = True

    PAY_ENDPOINT = "/pg/v1/pay"

    def __init__(self):
        self.merchant_id = ""
        self.salt_key = ""
        self.salt_index = "1"
        self.env = "sandbox"
        self.base_url = "https://api-preprod.phonepe.com/apis/pg-sandbox"

    def _load_runtime_config(self) -> None:
        merchant_id = str(getattr(settings, "PHONEPE_MERCHANT_ID", "") or "").strip()
        salt_key = str(getattr(settings, "PHONEPE_SALT_KEY", "") or "").strip()
        salt_index = str(getattr(settings, "PHONEPE_SALT_INDEX", "1") or "1").strip()
        env = str(getattr(settings, "PHONEPE_ENV", "sandbox") or "sandbox").strip().lower()

        try:
            from apps.features.models import AppSetting, ProviderConfig

            config: dict[str, Any] = {}
            setting = (
                AppSetting.objects
                .filter(key__in=[
                    "payment.phonepe",
                    "payment-phonepe",
                    "payment_phonepe",
                    "phonepe",
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
                        provider_key="phonepe",
                        is_active=True,
                        feature__category="payment",
                    )
                    .order_by("-updated_at")
                    .first()
                )
                if provider_row and isinstance(provider_row.config, dict):
                    config = provider_row.config

            if config:
                merchant_id = str(config.get("merchant_id") or merchant_id).strip()
                salt_key = str(config.get("salt_key") or salt_key).strip()
                salt_index = str(config.get("salt_index") or salt_index).strip()
                env = str(config.get("environment") or config.get("env") or env).strip().lower()
        except Exception:
            pass

        if env not in {"sandbox", "production"}:
            env = "sandbox"
        if not salt_index:
            salt_index = "1"

        self.merchant_id = merchant_id
        self.salt_key = salt_key
        self.salt_index = salt_index
        self.env = env
        self.base_url = (
            "https://api.phonepe.com/apis/hermes"
            if env == "production"
            else "https://api-preprod.phonepe.com/apis/pg-sandbox"
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

        if not self.merchant_id or not self.salt_key:
            return PaymentResult(
                success=False,
                provider_ref="",
                error="PhonePe credentials missing. Set merchant_id and salt_key in payment settings.",
            )

        # PhonePe expects amount in paise
        amount_paise = int(amount * 100)
        payload_dict = {
            "merchantId":            self.merchant_id,
            "merchantTransactionId": order_id,
            "amount":                amount_paise,
            "redirectUrl":           return_url or f"{getattr(settings, 'FRONTEND_URL', '')}/orders/{order_id}",
            "redirectMode":          "REDIRECT",
            "paymentInstrument":     {"type": "PAY_PAGE"},
        }
        payload_b64 = base64.b64encode(json.dumps(payload_dict).encode()).decode()
        checksum    = self._compute_checksum(payload_b64, self.PAY_ENDPOINT)

        try:
            resp = requests.post(
                f"{self.base_url}{self.PAY_ENDPOINT}",
                json={"request": payload_b64},
                headers={
                    "Content-Type":  "application/json",
                    "X-VERIFY":      checksum,
                    "X-MERCHANT-ID": self.merchant_id,
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            pay_url = (
                data.get("data", {})
                    .get("instrumentResponse", {})
                    .get("redirectInfo", {})
                    .get("url", "")
            )
            return PaymentResult(
                success=data.get("success", False),
                provider_ref=order_id,
                payment_url=pay_url,
                raw_response=data,
            )
        except Exception as exc:
            return PaymentResult(success=False, provider_ref="", error=str(exc))

    # ── Webhook ────────────────────────────────────────────────

    def verify_webhook(self, *, payload: bytes, headers: dict) -> WebhookResult:
        """
        PhonePe sends an x-verify header:
        SHA256(base64_payload + callback_url + salt_key) + "###" + salt_index
        """
        self._load_runtime_config()

        normalized_headers = {str(k).lower(): v for k, v in (headers or {}).items()}
        x_verify = str(normalized_headers.get("x-verify", "") or "").strip()
        if not x_verify:
            return WebhookResult(verified=False, provider_ref="", order_ref="",
                                 status="failed", amount=Decimal(0), currency="INR",
                                 error="Missing X-VERIFY header.")

        try:
            # PhonePe posts JSON with "response" key (base64-encoded)
            body       = json.loads(payload)
            response_b64 = body.get("response", "")
            event_data = json.loads(base64.b64decode(response_b64))

            # Verify checksum
            expected = self._compute_checksum(response_b64, "")
            provided_hash = x_verify.split("###")[0]

            if not _hmac.compare_digest(expected.split("###")[0], provided_hash):
                return WebhookResult(verified=False, provider_ref="", order_ref="",
                                     status="failed", amount=Decimal(0), currency="INR",
                                     error="Checksum mismatch.")

            txn    = event_data.get("data", {}).get("merchantTransactionId", "")
            code   = event_data.get("code", "")
            status = "success" if code == "PAYMENT_SUCCESS" else (
                "pending" if "PENDING" in code else "failed"
            )
            amount_paise = event_data.get("data", {}).get("amount", 0)

            return WebhookResult(
                verified=True,
                provider_ref=event_data.get("data", {}).get("transactionId", ""),
                order_ref=txn,
                status=status,
                amount=Decimal(amount_paise) / 100,
                currency="INR",
                raw_data=event_data,
            )
        except Exception as exc:
            return WebhookResult(verified=False, provider_ref="", order_ref="",
                                 status="failed", amount=Decimal(0), currency="INR",
                                 error=str(exc))

    # ── Refund ────────────────────────────────────────────────

    def refund(self, *, provider_ref: str, amount: Decimal, reason: str = "") -> RefundResult:
        import requests
        self._load_runtime_config()
        amount_paise = int(amount * 100)
        payload_dict = {
            "merchantId":            self.merchant_id,
            "merchantTransactionId": f"REFUND-{provider_ref}",
            "originalTransactionId": provider_ref,
            "amount":                amount_paise,
            "callbackUrl":           "",
        }
        endpoint = "/pg/v1/refund"
        payload_b64 = base64.b64encode(json.dumps(payload_dict).encode()).decode()
        checksum    = self._compute_checksum(payload_b64, endpoint)
        try:
            resp = requests.post(
                f"{self.base_url}{endpoint}",
                json={"request": payload_b64},
                headers={"Content-Type": "application/json", "X-VERIFY": checksum},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return RefundResult(
                success=data.get("success", False),
                refund_ref=data.get("data", {}).get("merchantTransactionId", ""),
                amount=amount,
                raw_response=data,
            )
        except Exception as exc:
            return RefundResult(success=False, refund_ref="", amount=amount, error=str(exc))

    # ── Status ────────────────────────────────────────────────

    def get_status(self, *, provider_ref: str) -> StatusResult:
        import requests
        self._load_runtime_config()
        endpoint    = f"/pg/v1/status/{self.merchant_id}/{provider_ref}"
        checksum    = self._compute_checksum("", endpoint)
        try:
            resp = requests.get(
                f"{self.base_url}{endpoint}",
                headers={"X-VERIFY": checksum, "X-MERCHANT-ID": self.merchant_id},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            code = data.get("code", "")
            status = "success" if code == "PAYMENT_SUCCESS" else (
                "pending" if "PENDING" in code else "failed"
            )
            return StatusResult(
                success=True,
                provider_ref=provider_ref,
                status=status,
                raw_response=data,
            )
        except Exception as exc:
            return StatusResult(success=False, provider_ref=provider_ref, status="failed", error=str(exc))

    # ── Private ───────────────────────────────────────────────

    def _compute_checksum(self, payload_b64: str, endpoint: str) -> str:
        data = payload_b64 + endpoint + self.salt_key
        sha256 = hashlib.sha256(data.encode()).hexdigest()
        return f"{sha256}###{self.salt_index}"
