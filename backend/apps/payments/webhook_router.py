from __future__ import annotations

from typing import Any


def route_event(payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """
    Route Cashfree webhook payload to payment/refund handlers.
    Returns:
      ("refund", refund_data) or ("payment", payment_data)
    Raises:
      ValueError for malformed payloads.
    """
    if not isinstance(payload, dict):
        raise ValueError("Payload must be a JSON object.")

    nested = payload.get("data")
    if not isinstance(nested, dict):
        raise ValueError("Missing data object in payload.")

    refund = nested.get("refund")
    if isinstance(refund, dict):
        return "refund", refund

    payment = nested.get("payment")
    if isinstance(payment, dict):
        return "payment", payment

    raise ValueError("Unsupported webhook event payload.")

