"""
payments.providers.stripe_provider
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Stripe Payments integration (Payment Intents API).

Docs: https://stripe.com/docs/api/payment_intents

Environment variables:
    STRIPE_SECRET_KEY       → sk_test_... / sk_live_...
    STRIPE_WEBHOOK_SECRET   → whsec_...  (from Stripe dashboard)
    STRIPE_PUBLISHABLE_KEY  → pk_test_... (sent to frontend)

Webhook signature:
    Stripe signs each event with a HMAC-SHA256 signature.
    Header: stripe-signature
    Verified via: stripe.Webhook.construct_event(payload, sig, webhook_secret)
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings

from .base import BasePaymentProvider, PaymentResult, WebhookResult, RefundResult, StatusResult


class StripeProvider(BasePaymentProvider):
    name                 = "stripe"
    display_name         = "Stripe"
    supported_currencies = ["USD", "EUR", "GBP", "INR", "AUD", "CAD", "SGD"]
    supports_refunds     = True
    supports_webhooks    = True

    def __init__(self):
        self.secret_key      = getattr(settings, "STRIPE_SECRET_KEY", "")
        self.webhook_secret  = getattr(settings, "STRIPE_WEBHOOK_SECRET", "")
        self.publishable_key = getattr(settings, "STRIPE_PUBLISHABLE_KEY", "")

    # ── Initiate ──────────────────────────────────────────────

    def initiate(
        self,
        *,
        order_id: str,
        amount: Decimal,
        currency: str = "inr",
        customer_email: str,
        customer_name: str,
        customer_phone: str = "",
        return_url: str = "",
        metadata: dict | None = None,
    ) -> PaymentResult:
        try:
            import stripe
            stripe.api_key = self.secret_key

            # Stripe uses smallest currency unit (paise for INR, cents for USD)
            amount_int = int(amount * 100)

            intent = stripe.PaymentIntent.create(
                amount=amount_int,
                currency=currency.lower(),
                receipt_email=customer_email,
                description=f"Aurora Blings Order {order_id}",
                metadata=self.build_metadata(order_id, metadata),
                automatic_payment_methods={"enabled": True},
            )
            return PaymentResult(
                success=True,
                provider_ref=intent.id,
                client_secret=intent.client_secret,   # used by Stripe.js on the frontend
                raw_response=dict(intent),
            )
        except Exception as exc:
            return PaymentResult(success=False, provider_ref="", error=str(exc))

    # ── Webhook ───────────────────────────────────────────────

    def verify_webhook(self, *, payload: bytes, headers: dict) -> WebhookResult:
        """
        Stripe uses cryptographic signature via:
            stripe.Webhook.construct_event(payload, sig_header, webhook_secret)

        This is the RECOMMENDED approach — do not implement manually.
        """
        try:
            import stripe
            stripe.api_key = self.secret_key

            sig_header = headers.get("stripe-signature", "")
            if not sig_header:
                return WebhookResult(verified=False, provider_ref="", order_ref="",
                                     status="failed", amount=Decimal(0), currency="",
                                     error="Missing stripe-signature header.")

            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )

            event_type      = event["type"]
            payment_intent  = event.get("data", {}).get("object", {})
            status_map      = {
                "payment_intent.succeeded":              "success",
                "payment_intent.payment_failed":         "failed",
                "payment_intent.processing":             "pending",
                "payment_intent.requires_payment_method": "failed",
            }
            status    = status_map.get(event_type, "pending")
            order_ref = payment_intent.get("metadata", {}).get("order_id", "")
            amount    = Decimal(payment_intent.get("amount", 0)) / 100
            currency  = payment_intent.get("currency", "").upper()

            return WebhookResult(
                verified=True,
                provider_ref=payment_intent.get("id", ""),
                order_ref=order_ref,
                status=status,
                amount=amount,
                currency=currency,
                raw_data=dict(event),
            )

        except Exception as exc:
            return WebhookResult(verified=False, provider_ref="", order_ref="",
                                 status="failed", amount=Decimal(0), currency="",
                                 error=str(exc))

    # ── Refund ────────────────────────────────────────────────

    def refund(self, *, provider_ref: str, amount: Decimal, reason: str = "") -> RefundResult:
        try:
            import stripe
            stripe.api_key = self.secret_key

            refund = stripe.Refund.create(
                payment_intent=provider_ref,
                amount=int(amount * 100),
                reason="requested_by_customer",
            )
            return RefundResult(
                success=refund.status == "succeeded",
                refund_ref=refund.id,
                amount=amount,
                raw_response=dict(refund),
            )
        except Exception as exc:
            return RefundResult(success=False, refund_ref="", amount=amount, error=str(exc))

    # ── Status ────────────────────────────────────────────────

    def get_status(self, *, provider_ref: str) -> StatusResult:
        try:
            import stripe
            stripe.api_key = self.secret_key

            intent     = stripe.PaymentIntent.retrieve(provider_ref)
            status_map = {
                "succeeded":         "success",
                "requires_payment_method": "failed",
                "canceled":          "failed",
                "processing":        "pending",
                "requires_action":   "pending",
            }
            return StatusResult(
                success=True,
                provider_ref=provider_ref,
                status=status_map.get(intent.status, "pending"),
                amount=Decimal(intent.amount) / 100,
                raw_response=dict(intent),
            )
        except Exception as exc:
            return StatusResult(success=False, provider_ref=provider_ref, status="failed", error=str(exc))
