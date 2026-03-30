from __future__ import annotations

import hashlib
import json
from typing import Any

from django.db import transaction

from core.logging import get_logger
from core.response import error_response, success_response

from apps.payments.models import WebhookEvent
from apps.payments.payment_service import handle_payment_failed, handle_payment_success
from apps.payments.refund_service import handle_refund_webhook as _handle_refund_webhook
from apps.payments.webhook_router import route_event
from apps.payments.webhooks.verification import verify_cashfree_webhook

logger = get_logger(__name__)

MAX_WEBHOOK_PAYLOAD_BYTES = 256 * 1024


def _extract_event_id(payload: dict[str, Any], payload_bytes: bytes) -> str:
    data = payload if isinstance(payload, dict) else {}
    nested = data.get("data") if isinstance(data.get("data"), dict) else {}
    candidates = (
        data.get("event_id"),
        data.get("id"),
        data.get("cf_event_id"),
        nested.get("event_id") if isinstance(nested, dict) else None,
    )
    for candidate in candidates:
        text = str(candidate or "").strip()
        if text:
            return text
    return hashlib.sha256(payload_bytes or b"").hexdigest()


def _extract_event_type(payload: dict[str, Any]) -> str:
    data = payload if isinstance(payload, dict) else {}
    return str(
        data.get("event_type")
        or data.get("type")
        or data.get("event")
        or ""
    ).strip()


@transaction.atomic
def process_cashfree_webhook_payload(*, payload: dict[str, Any], payload_bytes: bytes) -> dict[str, Any]:
    """
    Process a verified cashfree webhook payload with idempotency.
    """
    event_id = _extract_event_id(payload, payload_bytes)
    event_type = _extract_event_type(payload)

    event, created = WebhookEvent.objects.select_for_update().get_or_create(
        event_id=event_id,
        defaults={
            "event_type": event_type,
            "payload": payload,
            "processed": False,
        },
    )

    if not created and event.processed:
        logger.info("cashfree_webhook_duplicate_skip", event_id=event_id, event_type=event.event_type)
        return {"duplicate": True, "event_id": event_id, "event_type": event.event_type}

    if created:
        logger.info("cashfree_webhook_event_created", event_id=event_id, event_type=event_type)
    else:
        event.event_type = event_type or event.event_type
        event.payload = payload
        event.save(update_fields=["event_type", "payload"])

    routed_type, routed_data = route_event(payload)
    nested = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    order_data = nested.get("order") if isinstance(nested.get("order"), dict) else {}
    if routed_type == "refund":
        _handle_refund_webhook(refund_data=routed_data, provider_name="cashfree")
    else:
        # Cashfree payment webhooks often split order + payment objects.
        # Enrich payment payload so downstream lookup can resolve transaction.
        payment_payload = dict(routed_data or {})
        if isinstance(order_data, dict):
            payment_payload.setdefault("order_id", order_data.get("order_id") or order_data.get("id"))
            payment_payload.setdefault("cf_order_id", order_data.get("cf_order_id"))
        status = str(payment_payload.get("payment_status") or payment_payload.get("status") or "").upper()
        if status == "SUCCESS":
            handle_payment_success(payment_data=payment_payload, provider_name="cashfree")
        elif status in {"FAILED", "CANCELLED"}:
            handle_payment_failed(payment_data=payment_payload, provider_name="cashfree")
        else:
            logger.info("cashfree_webhook_payment_status_ignored", event_id=event_id, payment_status=status)

    event.processed = True
    event.save(update_fields=["processed"])
    logger.info("cashfree_webhook_processed", event_id=event_id, event_type=routed_type)
    return {"duplicate": False, "event_id": event_id, "event_type": routed_type}


def cashfree_webhook(request):
    """
    Hardened Cashfree webhook endpoint.

    Response rules:
      - 200 for processed/duplicate
      - 403 for signature failure
      - 400 for malformed payload
    """
    if request.method != "POST":
        return error_response(
            message="Method not allowed.",
            error_code="method_not_allowed",
            status_code=405,
        )

    payload_bytes = request.body or b""
    if len(payload_bytes) > MAX_WEBHOOK_PAYLOAD_BYTES:
        logger.warning("cashfree_webhook_payload_too_large", size=len(payload_bytes))
        return error_response(
            message="Webhook payload too large.",
            error_code="payload_too_large",
            status_code=400,
        )

    if not verify_cashfree_webhook(request):
        logger.warning("cashfree_webhook_signature_invalid")
        return error_response(
            message="Invalid webhook signature.",
            error_code="invalid_signature",
            status_code=403,
        )

    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        logger.warning("cashfree_webhook_malformed_json")
        return error_response(
            message="Malformed webhook payload.",
            error_code="malformed_payload",
            status_code=400,
        )

    try:
        result = process_cashfree_webhook_payload(payload=payload, payload_bytes=payload_bytes)
    except ValueError as exc:
        logger.warning("cashfree_webhook_route_error", error=str(exc))
        return error_response(
            message=str(exc),
            error_code="malformed_payload",
            status_code=400,
        )

    return success_response(data=result, message="Webhook processed.")


def handle_refund_webhook(*, refund_data: dict[str, Any], provider_name: str = "cashfree"):
    """
    Backward-compatible import path used by existing payment service.
    """
    return _handle_refund_webhook(refund_data=refund_data, provider_name=provider_name)
