"""
payments.providers.base
~~~~~~~~~~~~~~~~~~~~~~~
Abstract base class that every payment provider must implement.

Contract:
  - initiate()        → PaymentResult  (create a payment session / order)
  - verify_webhook()  → WebhookResult  (validate + parse incoming webhook)
  - refund()          → RefundResult   (issue a partial or full refund)
  - get_status()      → StatusResult   (poll provider for payment status)

All providers must declare:
  name         : str   (unique key, e.g. "cashfree")
  display_name : str   (human label, e.g. "Cashfree")
  supported_currencies : list[str]
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


# ─────────────────────────────────────────────────────────────
#  Shared result dataclasses
# ─────────────────────────────────────────────────────────────

@dataclass
class PaymentResult:
    """Returned by BasePaymentProvider.initiate()"""
    success:        bool
    provider_ref:   str                       # provider's order/transaction ID
    payment_url:    str | None = None         # hosted page redirect URL (if any)
    client_secret:  str | None = None         # Stripe client_secret etc.
    qr_code:        str | None = None         # UPI/PhonePe QR
    raw_response:   dict       = field(default_factory=dict)
    error:          str | None = None


@dataclass
class CheckoutOrderResult:
    """Returned by provider.create_checkout_order()"""
    success: bool
    provider_ref: str                      # provider order/reference id
    amount: Decimal
    currency: str
    key_id: str | None = None
    raw_response: dict = field(default_factory=dict)
    error: str | None = None


@dataclass
class VerificationResult:
    """Returned by provider.verify_payment_signature()"""
    success: bool
    provider_ref: str                      # provider payment id
    order_ref: str                         # our order ID / reference
    raw_response: dict = field(default_factory=dict)
    error: str | None = None


@dataclass
class WebhookResult:
    """Returned by BasePaymentProvider.verify_webhook()"""
    verified:     bool
    provider_ref: str                         # provider's transaction ID
    order_ref:    str                         # our order ID / reference
    status:       str                         # "success" | "failed" | "pending"
    amount:       Decimal
    currency:     str
    raw_data:     dict  = field(default_factory=dict)
    error:        str | None = None


@dataclass
class RefundResult:
    """Returned by BasePaymentProvider.refund()"""
    success:      bool
    refund_ref:   str                         # provider's refund ID
    amount:       Decimal
    raw_response: dict  = field(default_factory=dict)
    error:        str | None = None


@dataclass
class StatusResult:
    """Returned by BasePaymentProvider.get_status()"""
    success:      bool
    status:       str                         # "success" | "failed" | "pending"
    provider_ref: str
    amount:       Decimal | None = None
    raw_response: dict  = field(default_factory=dict)
    error:        str | None = None


# ─────────────────────────────────────────────────────────────
#  Base provider
# ─────────────────────────────────────────────────────────────

class BasePaymentProvider(abc.ABC):
    """
    Abstract interface for all payment providers.

    Implementors register themselves in the provider registry via:
        registry.register(MyProvider())
    """

    name:                 str   = ""
    display_name:         str   = ""
    supported_currencies: list  = field(default_factory=list)
    supports_refunds:     bool  = True
    supports_webhooks:    bool  = True

    # ── Must implement ────────────────────────────────────────

    @abc.abstractmethod
    def initiate(
        self,
        *,
        order_id: str,
        amount: Decimal,
        currency: str,
        customer_email: str,
        customer_name: str,
        customer_phone: str = "",
        return_url: str = "",
        metadata: dict | None = None,
    ) -> PaymentResult:
        """
        Create a payment session/order with the provider.

        Should return:
          PaymentResult(
              success=True,
              provider_ref="<provider_order_id>",
              payment_url="https://...",   # redirect the customer here
          )
        """
        ...

    @abc.abstractmethod
    def verify_webhook(
        self,
        *,
        payload: bytes,
        headers: dict,
    ) -> WebhookResult:
        """
        Validate the webhook signature and parse the event.

        payload: raw request body bytes (BEFORE any JSON parsing)
        headers: dict of HTTP headers (lowercase keys)

        Returns:
          WebhookResult(
              verified=True,
              provider_ref="...",
              order_ref="...",      # our order ID that we passed to initiate()
              status="success",
              amount=Decimal("999.00"),
              currency="INR",
          )
        """
        ...

    @abc.abstractmethod
    def refund(
        self,
        *,
        provider_ref: str,
        amount: Decimal,
        reason: str = "",
    ) -> RefundResult:
        """Issue a refund for the given provider transaction/order."""
        ...

    @abc.abstractmethod
    def get_status(self, *, provider_ref: str) -> StatusResult:
        """Poll provider for the current payment status."""
        ...

    # ── Utility ───────────────────────────────────────────────

    def build_metadata(self, order_id: str, extra: dict | None = None) -> dict:
        """Standard metadata dict attached to all provider API calls."""
        return {
            "order_id": order_id,
            "platform": "aurora_blings",
            **(extra or {}),
        }

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
        raise NotImplementedError(f"{self.__class__.__name__} does not support checkout order creation.")

    def verify_payment_signature(
        self,
        *,
        provider_order_id: str,
        provider_payment_id: str,
        signature: str,
    ) -> VerificationResult:
        raise NotImplementedError(f"{self.__class__.__name__} does not support payment signature verification.")
