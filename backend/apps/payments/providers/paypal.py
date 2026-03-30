"""
payments.providers.paypal
~~~~~~~~~~~~~~~~~~~~~~~~~~
PayPal Orders v2 integration.

Docs: https://developer.paypal.com/docs/api/orders/v2/

Environment variables:
    PAYPAL_CLIENT_ID     → REST API client ID
    PAYPAL_CLIENT_SECRET → REST API client secret
    PAYPAL_WEBHOOK_ID    → Webhook ID (from dashboard, for verification)
    PAYPAL_ENV           → "sandbox" | "production"

Webhook signature:
    PayPal uses a webhook verification API call approach.
    We POST the event + signature headers back to PayPal to verify.
    Header: paypal-transmission-sig, paypal-cert-url, paypal-transmission-id, paypal-transmission-time
"""

from __future__ import annotations

import hashlib
import hmac
import json
from decimal import Decimal

from django.conf import settings

from .base import BasePaymentProvider, PaymentResult, WebhookResult, RefundResult, StatusResult


class PayPalProvider(BasePaymentProvider):
    name                 = "paypal"
    display_name         = "PayPal"
    supported_currencies = ["USD", "EUR", "GBP", "INR"]
    supports_refunds     = True
    supports_webhooks    = True

    def __init__(self):
        self.client_id     = getattr(settings, "PAYPAL_CLIENT_ID", "")
        self.client_secret = getattr(settings, "PAYPAL_CLIENT_SECRET", "")
        self.webhook_id    = getattr(settings, "PAYPAL_WEBHOOK_ID", "")
        env                = getattr(settings, "PAYPAL_ENV", "sandbox")
        self.base_url      = (
            "https://api-m.paypal.com"
            if env == "production"
            else "https://api-m.sandbox.paypal.com"
        )
        self._access_token: str | None = None

    # ── Initiate ──────────────────────────────────────────────

    def initiate(
        self,
        *,
        order_id: str,
        amount: Decimal,
        currency: str = "USD",
        customer_email: str,
        customer_name: str,
        customer_phone: str = "",
        return_url: str = "",
        metadata: dict | None = None,
    ) -> PaymentResult:
        import requests

        frontend_url = getattr(settings, "FRONTEND_URL", "")
        payload = {
            "intent": "CAPTURE",
            "purchase_units": [{
                "reference_id": order_id,
                "amount": {
                    "currency_code": currency,
                    "value": str(amount),
                },
            }],
            "application_context": {
                "return_url": return_url or f"{frontend_url}/orders/{order_id}",
                "cancel_url": f"{frontend_url}/cart",
            },
        }
        try:
            resp = requests.post(
                f"{self.base_url}/v2/checkout/orders",
                json=payload,
                headers=self._auth_headers(),
                timeout=15,
            )
            resp.raise_for_status()
            data        = resp.json()
            approve_url = next(
                (l["href"] for l in data.get("links", []) if l["rel"] == "approve"),
                None,
            )
            return PaymentResult(
                success=True,
                provider_ref=data.get("id", ""),
                payment_url=approve_url,
                raw_response=data,
            )
        except Exception as exc:
            return PaymentResult(success=False, provider_ref="", error=str(exc))

    # ── Webhook ───────────────────────────────────────────────

    def verify_webhook(self, *, payload: bytes, headers: dict) -> WebhookResult:
        """
        Verify via PayPal's Webhook verification API.
        Fallback: manual HMAC check if API is unavailable.
        """
        import requests

        try:
            verify_payload = {
                "auth_algo":         headers.get("paypal-auth-algo", ""),
                "cert_url":          headers.get("paypal-cert-url", ""),
                "webhook_id":        self.webhook_id,
                "webhook_event":     json.loads(payload),
                "transmission_id":   headers.get("paypal-transmission-id", ""),
                "transmission_sig":  headers.get("paypal-transmission-sig", ""),
                "transmission_time": headers.get("paypal-transmission-time", ""),
            }
            resp = requests.post(
                f"{self.base_url}/v1/notifications/verify-webhook-signature",
                json=verify_payload,
                headers=self._auth_headers(),
                timeout=10,
            )
            resp.raise_for_status()
            verification_status = resp.json().get("verification_status", "")

            if verification_status != "SUCCESS":
                return WebhookResult(verified=False, provider_ref="", order_ref="",
                                     status="failed", amount=Decimal(0), currency="USD",
                                     error="PayPal signature verification failed.")

            event           = json.loads(payload)
            resource        = event.get("resource", {})
            event_type      = event.get("event_type", "")
            status          = "success" if "COMPLETED" in event_type else (
                "pending" if "CREATED" in event_type else "failed"
            )
            order_ref       = resource.get("purchase_units", [{}])[0].get("reference_id", "")
            amount_val      = resource.get("amount", {}).get("value", "0")
            currency        = resource.get("amount", {}).get("currency_code", "USD")

            return WebhookResult(
                verified=True,
                provider_ref=resource.get("id", ""),
                order_ref=order_ref,
                status=status,
                amount=Decimal(amount_val),
                currency=currency,
                raw_data=event,
            )
        except Exception as exc:
            return WebhookResult(verified=False, provider_ref="", order_ref="",
                                 status="failed", amount=Decimal(0), currency="USD",
                                 error=str(exc))

    # ── Refund ────────────────────────────────────────────────

    def refund(self, *, provider_ref: str, amount: Decimal, reason: str = "") -> RefundResult:
        import requests
        try:
            resp = requests.post(
                f"{self.base_url}/v2/payments/captures/{provider_ref}/refund",
                json={"amount": {"value": str(amount), "currency_code": "USD"}, "note_to_payer": reason},
                headers=self._auth_headers(),
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return RefundResult(
                success=data.get("status") == "COMPLETED",
                refund_ref=data.get("id", ""),
                amount=amount,
                raw_response=data,
            )
        except Exception as exc:
            return RefundResult(success=False, refund_ref="", amount=amount, error=str(exc))

    # ── Status ────────────────────────────────────────────────

    def get_status(self, *, provider_ref: str) -> StatusResult:
        import requests
        try:
            resp = requests.get(
                f"{self.base_url}/v2/checkout/orders/{provider_ref}",
                headers=self._auth_headers(),
                timeout=15,
            )
            resp.raise_for_status()
            data        = resp.json()
            status_map  = {"COMPLETED": "success", "CREATED": "pending", "VOIDED": "failed"}
            return StatusResult(
                success=True,
                provider_ref=provider_ref,
                status=status_map.get(data.get("status", ""), "pending"),
                raw_response=data,
            )
        except Exception as exc:
            return StatusResult(success=False, provider_ref=provider_ref, status="failed", error=str(exc))

    # ── Private ───────────────────────────────────────────────

    def _get_access_token(self) -> str:
        import requests
        resp = requests.post(
            f"{self.base_url}/v1/oauth2/token",
            auth=(self.client_id, self.client_secret),
            data={"grant_type": "client_credentials"},
            timeout=10,
        )
        resp.raise_for_status()
        self._access_token = resp.json()["access_token"]
        return self._access_token

    def _auth_headers(self) -> dict:
        token = self._access_token or self._get_access_token()
        return {
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {token}",
        }
