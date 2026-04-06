"""
payments.services
~~~~~~~~~~~~~~~~~

Public API:
    initiate_payment(order, provider_name, ...)  → PaymentTransaction
    handle_webhook(provider_name, payload, headers) → WebhookLog
    retry_payment(transaction)                   → PaymentTransaction
    refund_payment(transaction, amount, reason)  → RefundResult

Flows:
  INITIATE:
    registry.get(provider_name)
    → provider.initiate()
    → PaymentTransaction.objects.create(status=PENDING)

  WEBHOOK:
    1. Log raw payload (before verification) → WebhookLog
    2. Check idempotency key — skip if already processed
    3. provider.verify_webhook() → WebhookResult
    4. Update WebhookLog.is_verified
    5. Find matching PaymentTransaction by provider_ref or order_ref
    6. Update transaction.status
    7. If SUCCESS → orders.services.mark_paid()
    8. Mark WebhookLog.is_processed = True

  RETRY (via Celery task):
    If transaction.can_retry:
      retry_count += 1
      provider.initiate() again
      update transaction with new provider_ref
"""

from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import transaction
from django.utils import timezone

from core.exceptions import ValidationError, NotFoundError
from core.logging import get_logger

from apps.payments.providers.registry import registry
from apps.payments.providers.base import WebhookResult
from .models import PaymentTransaction, WebhookLog, TransactionStatus

logger = get_logger(__name__)


def _normalize_customer_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", str(raw or ""))
    if digits.startswith("91") and len(digits) > 10:
        digits = digits[-10:]
    if len(digits) > 15:
        digits = digits[:15]
    return digits


def _get_order_customer_context(order) -> dict[str, str]:
    customer = order.user
    shipping_snapshot = order.shipping_address if isinstance(order.shipping_address, dict) else {}
    customer_email = (
        (customer.email if customer else "") or
        str(order.guest_email or "").strip() or
        str(shipping_snapshot.get("email") or "").strip()
    )
    customer_name = (
        (customer.get_full_name() if customer and hasattr(customer, "get_full_name") else "") or
        str(shipping_snapshot.get("full_name") or "").strip() or
        "Guest Customer"
    )
    raw_phone = (
        getattr(customer, "phone_number", "") if customer else ""
    ) or (
        getattr(customer, "phone", "") if customer else ""
    ) or str(shipping_snapshot.get("phone") or "").strip()
    customer_phone = _normalize_customer_phone(raw_phone)
    return {
        "email": customer_email,
        "name": customer_name,
        "phone": customer_phone,
    }


# ─────────────────────────────────────────────────────────────
#  1.  Initiate Payment
# ─────────────────────────────────────────────────────────────

@transaction.atomic
def initiate_payment(
    *,
    order,
    provider_name: str,
    currency: str | None = None,
    return_url: str = "",
    initiated_by=None,
) -> PaymentTransaction:
    """
    Start a payment session with the chosen provider.

    Returns a PaymentTransaction containing:
      - payment_url → redirect customer here (hosted pages)
      - client_secret → pass to Stripe.js for embedded flow

    Raises:
        KeyError        → unknown provider
        ValidationError → provider doesn't support the order currency
    """
    provider = registry.get(provider_name)
    currency = currency or order.currency

    if currency not in provider.supported_currencies:
        raise ValidationError(
            f"Provider '{provider_name}' does not support currency '{currency}'. "
            f"Supported: {provider.supported_currencies}"
        )

    customer_context = _get_order_customer_context(order)

    # Call provider
    result = provider.initiate(
        order_id=str(order.id),
        amount=order.grand_total,
        currency=currency,
        customer_email=customer_context["email"],
        customer_name=customer_context["name"],
        customer_phone=customer_context["phone"],
        return_url=return_url,
    )

    txn = PaymentTransaction.objects.create(
        order=order,
        provider=provider_name,
        provider_ref=result.provider_ref,
        status=TransactionStatus.PENDING if result.success else TransactionStatus.FAILED,
        total_amount=order.grand_total,
        refunded_amount=Decimal("0"),
        amount=order.grand_total,
        currency=currency,
        payment_url=result.payment_url or "",
        client_secret=result.client_secret or "",
        last_error=result.error or "",
        raw_response=result.raw_response,
        initiated_by=initiated_by,
    )

    log_level = "info" if result.success else "warning"
    getattr(logger, log_level)(
        "payment_initiated",
        order_number=order.order_number,
        provider=provider_name,
        transaction_id=str(txn.id),
        success=result.success,
    )
    return txn


@transaction.atomic
def create_checkout_order(
    *,
    order,
    provider_name: str,
    amount: Decimal | None = None,
    currency: str | None = None,
    initiated_by=None,
) -> PaymentTransaction:
    """
    Create a provider-native checkout order for modal SDK flows.

    For Razorpay this creates an `order_*` reference used by checkout.js.
    """
    provider = registry.get(provider_name)

    currency = (currency or order.currency or "INR").upper()
    expected_amount = Decimal(str(order.grand_total)).quantize(Decimal("0.01"))
    requested_amount = Decimal(str(amount if amount is not None else expected_amount)).quantize(Decimal("0.01"))

    if requested_amount != expected_amount:
        raise ValidationError("Requested amount does not match order total.")
    if currency != str(order.currency or "INR").upper():
        raise ValidationError("Requested currency does not match order currency.")
    if currency not in provider.supported_currencies:
        raise ValidationError(
            f"Provider '{provider_name}' does not support currency '{currency}'. "
            f"Supported: {provider.supported_currencies}"
        )

    customer_context = _get_order_customer_context(order)
    try:
        result = provider.create_checkout_order(
            order_id=str(order.id),
            amount=requested_amount,
            currency=currency,
            customer_email=customer_context["email"],
            customer_name=customer_context["name"],
            customer_phone=customer_context["phone"],
            metadata={"customer_email": customer_context["email"]},
        )
    except NotImplementedError as exc:
        raise ValidationError(f"Provider '{provider_name}' does not support checkout order creation.") from exc
    txn = PaymentTransaction.objects.create(
        order=order,
        provider=provider_name,
        provider_ref=result.provider_ref,
        razorpay_order_id=result.provider_ref if provider_name == "razorpay" else "",
        status=TransactionStatus.CREATED if result.success else TransactionStatus.FAILED,
        total_amount=requested_amount,
        refunded_amount=Decimal("0"),
        amount=requested_amount,
        currency=currency,
        last_error=result.error or "",
        raw_response=result.raw_response,
        initiated_by=initiated_by,
    )
    log_level = "info" if result.success else "warning"
    getattr(logger, log_level)(
        "payment_checkout_order_created",
        provider=provider_name,
        order_id=str(order.id),
        transaction_id=str(txn.id),
        provider_ref=result.provider_ref,
        success=result.success,
    )
    return txn


@transaction.atomic
def verify_checkout_payment(
    *,
    provider_name: str,
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str,
) -> PaymentTransaction:
    provider = registry.get(provider_name)
    try:
        verification = provider.verify_payment_signature(
            provider_order_id=razorpay_order_id,
            provider_payment_id=razorpay_payment_id,
            signature=razorpay_signature,
        )
    except NotImplementedError as exc:
        raise ValidationError(f"Provider '{provider_name}' does not support payment verification.") from exc
    from .selectors import get_transaction_by_razorpay_order_id

    txn = get_transaction_by_razorpay_order_id(razorpay_order_id)
    if txn is None:
        raise NotFoundError("Payment transaction not found for the provided Razorpay order.")

    txn.razorpay_order_id = razorpay_order_id
    txn.razorpay_payment_id = razorpay_payment_id
    txn.razorpay_signature = razorpay_signature
    raw = txn.raw_response if isinstance(txn.raw_response, dict) else {}
    raw.update(
        {
            "razorpay_order_id": razorpay_order_id,
            "razorpay_payment_id": razorpay_payment_id,
            "razorpay_signature_verified": verification.success,
        }
    )
    txn.raw_response = raw
    txn.last_error = "" if verification.success else (verification.error or "Razorpay signature verification failed.")

    if verification.success:
        txn.provider_ref = razorpay_payment_id or txn.provider_ref
        txn.save(
            update_fields=[
                "provider_ref",
                "razorpay_order_id",
                "razorpay_payment_id",
                "razorpay_signature",
                "last_error",
                "raw_response",
                "updated_at",
            ]
        )
        from .payment_service import handle_payment_success

        handle_payment_success(
            payment_data={
                "order_id": str(txn.order_id),
                "payment_id": razorpay_payment_id,
                "amount": str(txn.total_amount),
                "currency": txn.currency,
            },
            provider_name=provider_name,
        )
    else:
        txn.save(
            update_fields=[
                "razorpay_order_id",
                "razorpay_payment_id",
                "razorpay_signature",
                "last_error",
                "raw_response",
                "updated_at",
            ]
        )
        from .payment_service import handle_payment_failed

        handle_payment_failed(
            payment_data={
                "order_id": str(txn.order_id),
                "payment_id": razorpay_payment_id,
            },
            provider_name=provider_name,
        )

    txn.refresh_from_db()
    logger.info(
        "payment_signature_verified",
        provider=provider_name,
        transaction_id=str(txn.id),
        order_id=str(txn.order_id),
        razorpay_order_id=razorpay_order_id,
        razorpay_payment_id=razorpay_payment_id,
        success=verification.success,
    )
    return txn


# ─────────────────────────────────────────────────────────────
#  2.  Handle Webhook
# ─────────────────────────────────────────────────────────────

def handle_webhook(
    *,
    provider_name: str,
    payload: bytes,
    headers: dict,
) -> WebhookLog:
    """
    Process an incoming webhook:
      1. Log raw payload (always — even before verification)
      2. Idempotency check
      3. Verify signature
      4. Update transaction + order status
    """
    provider = registry.get(provider_name)

    # ── 1. Log raw payload ────────────────────────────────────
    webhook_log = WebhookLog.objects.create(
        provider=provider_name,
        raw_headers=dict(headers),
        raw_payload=payload.decode("utf-8", errors="replace"),
    )
    logger.info("webhook_received", provider=provider_name, log_id=str(webhook_log.id))

    # ── 2. Verify + parse ─────────────────────────────────────
    result: WebhookResult = provider.verify_webhook(payload=payload, headers=headers)

    webhook_log.is_verified = result.verified
    if not result.verified:
        webhook_log.processing_error = result.error or "Signature verification failed."
        webhook_log.save(update_fields=["is_verified", "processing_error"])
        logger.warning(
            "webhook_verification_failed",
            provider=provider_name,
            error=result.error,
        )
        return webhook_log

    # ── 3. Idempotency check ──────────────────────────────────
    provider_event_id = _extract_provider_event_id(result.raw_data)
    if provider_event_id:
        webhook_log.provider_event_id = provider_event_id

    idem_key = _build_idempotency_key(
        provider_name=provider_name,
        provider_event_id=provider_event_id,
        provider_ref=result.provider_ref,
        order_ref=result.order_ref,
        status=result.status,
        payload=payload,
    )
    if idem_key:
        webhook_log.idempotency_key = idem_key
        if WebhookLog.objects.filter(
            idempotency_key=idem_key,
            is_processed=True,
        ).exclude(pk=webhook_log.pk).exists():
            webhook_log.processing_error = "Duplicate webhook — already processed."
            webhook_log.is_processed     = True
            webhook_log.save(
                update_fields=[
                    "provider_event_id",
                    "idempotency_key",
                    "processing_error",
                    "is_processed",
                ]
            )
            logger.info("webhook_duplicate_skipped", idem_key=idem_key)
            return webhook_log

    # ── 4. Update fields on the log ───────────────────────────
    webhook_log.provider_ref  = result.provider_ref
    webhook_log.order_ref     = result.order_ref
    webhook_log.event_status  = result.status
    webhook_log.idempotency_key = idem_key

    # ── 5. Find matching transaction ──────────────────────────
    txn = (
        PaymentTransaction.objects
        .filter(order__id=result.order_ref, provider=provider_name)
        .order_by("-created_at")
        .first()
    )
    if not txn:
        txn = (
            PaymentTransaction.objects
            .filter(provider_ref=result.provider_ref, provider=provider_name)
            .order_by("-created_at")
            .first()
        )

    try:
        if provider_name == "cashfree":
            refund_payload = _extract_cashfree_refund_payload(result.raw_data)
            if refund_payload:
                from .webhooks.cashfree_webhook import handle_refund_webhook

                refund = handle_refund_webhook(refund_data=refund_payload, provider_name=provider_name)
                webhook_log.is_processed = True
                if refund and refund.payment_id:
                    webhook_log.transaction_id = refund.payment_id
                logger.info(
                    "cashfree_refund_webhook_processed",
                    provider=provider_name,
                    order_ref=result.order_ref,
                    refund_id=getattr(refund, "refund_id", ""),
                    status=result.status,
                )
            elif txn:
                _update_transaction_from_webhook(txn, result, webhook_log)
                webhook_log.is_processed = True
            else:
                webhook_log.processing_error = "No matching transaction found."
                logger.warning(
                    "webhook_transaction_not_found",
                    provider=provider_name,
                    order_ref=result.order_ref,
                    provider_ref=result.provider_ref,
                )
        elif txn:
            _update_transaction_from_webhook(txn, result, webhook_log)
            webhook_log.is_processed = True
        else:
            webhook_log.processing_error = "No matching transaction found."
            logger.warning(
                "webhook_transaction_not_found",
                provider=provider_name,
                order_ref=result.order_ref,
                provider_ref=result.provider_ref,
            )
        logger.info("webhook_processed", provider=provider_name, order_ref=result.order_ref, status=result.status)
    except Exception as exc:
        webhook_log.processing_error = str(exc)
        logger.exception("webhook_processing_error", provider=provider_name, error=str(exc))

    webhook_log.save(
        update_fields=[
            "provider_event_id", "provider_ref", "order_ref", "event_status",
            "idempotency_key", "is_processed", "processing_error",
            "transaction",
        ]
    )
    return webhook_log


def _update_transaction_from_webhook(txn: PaymentTransaction, result: WebhookResult, log: WebhookLog):
    """Apply webhook status to the transaction and trigger order state transitions.

    Guards:
      - State machine: only valid transitions are applied
      - Amount/currency verification on success: mismatch blocks mark_paid
    """
    from apps.orders.services import mark_paid

    status_map = {
        "success": TransactionStatus.SUCCESS,
        "failed":  TransactionStatus.FAILED,
        "pending": TransactionStatus.PENDING,
    }
    desired_status = status_map.get(result.status, TransactionStatus.PENDING)

    # ── State machine guard ───────────────────────────────────
    allowed_success_from = {TransactionStatus.CREATED, TransactionStatus.PENDING, TransactionStatus.RETRY, TransactionStatus.FAILED}
    allowed_failed_from = {TransactionStatus.CREATED, TransactionStatus.PENDING, TransactionStatus.RETRY}

    if desired_status == TransactionStatus.SUCCESS and txn.status == TransactionStatus.SUCCESS:
        # Idempotent: already succeeded
        log.transaction = txn
        return
    if desired_status == TransactionStatus.SUCCESS and txn.status not in allowed_success_from:
        logger.warning(
            "webhook_invalid_transition",
            transaction_id=str(txn.id),
            current_status=txn.status,
            desired_status="success",
            provider=txn.provider,
        )
        log.transaction = txn
        return
    if desired_status == TransactionStatus.FAILED and txn.status not in allowed_failed_from:
        if txn.status != TransactionStatus.FAILED:  # idempotent skip
            logger.warning(
                "webhook_invalid_transition",
                transaction_id=str(txn.id),
                current_status=txn.status,
                desired_status="failed",
                provider=txn.provider,
            )
        log.transaction = txn
        return

    # ── Amount & currency verification (on success) ───────────
    if desired_status == TransactionStatus.SUCCESS:
        amount_ok, mismatch_reason = _verify_webhook_amount(txn=txn, result=result)
        if not amount_ok:
            logger.warning(
                "webhook_amount_mismatch",
                transaction_id=str(txn.id),
                order_id=str(txn.order_id),
                provider=txn.provider,
                mismatch_reason=mismatch_reason,
            )
            log.transaction = txn
            return

    txn.status = desired_status
    if txn.provider == "cashfree":
        # Keep provider_ref as cf_order_id for reconciliation/refund APIs.
        raw = txn.raw_response if isinstance(txn.raw_response, dict) else {}
        if result.provider_ref:
            raw["cf_payment_id"] = result.provider_ref
        txn.raw_response = raw
        txn.save(update_fields=["status", "raw_response", "updated_at"])
    elif txn.provider == "razorpay":
        raw = txn.raw_response if isinstance(txn.raw_response, dict) else {}
        provider_order_id = str((result.raw_data or {}).get("_provider_order_id") or txn.razorpay_order_id or "").strip()
        if provider_order_id:
            raw["razorpay_order_id"] = provider_order_id
        if result.provider_ref:
            raw["razorpay_payment_id"] = result.provider_ref
        txn.provider_ref = result.provider_ref or txn.provider_ref
        txn.razorpay_order_id = provider_order_id or txn.razorpay_order_id
        txn.razorpay_payment_id = result.provider_ref or txn.razorpay_payment_id
        txn.raw_response = raw
        txn.save(
            update_fields=[
                "status",
                "provider_ref",
                "razorpay_order_id",
                "razorpay_payment_id",
                "raw_response",
                "updated_at",
            ]
        )
    else:
        txn.provider_ref = result.provider_ref or txn.provider_ref
        txn.save(update_fields=["status", "provider_ref", "updated_at"])
    log.transaction = txn

    order = txn.order
    if result.status == "success" and order.status in ("placed", "draft"):
        mark_paid(
            order=order,
            payment_reference=result.provider_ref,
            payment_method=txn.provider,
        )
    elif result.status == "failed":
        logger.warning(
            "payment_failed",
            order_number=order.order_number,
            provider=txn.provider,
            provider_ref=result.provider_ref,
        )


def _verify_webhook_amount(
    *, txn: PaymentTransaction, result: WebhookResult,
) -> tuple[bool, str]:
    """Compare WebhookResult amount/currency with transaction record."""
    if result.amount is None or result.amount == Decimal(0):
        # Provider didn't report amount — can't verify, allow through
        return True, ""
    try:
        provider_amount = Decimal(str(result.amount)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError):
        return False, f"Unparseable provider amount: {result.amount}"

    expected = txn.total_amount.quantize(Decimal("0.01"))
    if provider_amount != expected:
        return False, f"Amount mismatch: provider={provider_amount}, expected={expected}"
    if result.currency and result.currency.upper() != txn.currency.upper():
        return False, f"Currency mismatch: provider={result.currency}, expected={txn.currency}"
    return True, ""


def _extract_cashfree_refund_payload(raw_data: dict[str, Any] | None) -> dict[str, Any] | None:
    """
    Return refund payload if this Cashfree event represents a refund update.
    """
    data = raw_data or {}
    nested = data.get("data")
    if not isinstance(nested, dict):
        return None
    refund = nested.get("refund")
    if isinstance(refund, dict):
        return refund
    return None


def _extract_provider_event_id(raw_data: dict[str, Any] | None) -> str:
    """
    Best-effort extraction of provider event id for idempotency.
    Falls back to empty string if no stable event identifier is present.
    """
    data = raw_data or {}
    candidates = (
        data.get("event_id"),
        data.get("id"),
        data.get("cf_event_id"),
        data.get("cf_webhook_id"),
        (data.get("data") or {}).get("event_id") if isinstance(data.get("data"), dict) else None,
    )
    for value in candidates:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _build_idempotency_key(
    *,
    provider_name: str,
    provider_event_id: str,
    provider_ref: str,
    order_ref: str,
    status: str,
    payload: bytes,
) -> str:
    """
    Build a webhook idempotency key.
    Priority:
      1) provider event id (most reliable)
      2) provider ref + status (so pending/success are not collapsed)
      3) order ref + status
      4) payload hash fallback
    """
    if provider_event_id:
        return f"{provider_name}:event:{provider_event_id}"
    if provider_ref:
        return f"{provider_name}:ref:{provider_ref}:{status or 'unknown'}"
    if order_ref:
        return f"{provider_name}:order:{order_ref}:{status or 'unknown'}"
    digest = hashlib.sha256(payload or b"").hexdigest()[:24]
    return f"{provider_name}:raw:{digest}"
@transaction.atomic
def reconcile_transaction_status(*, transaction: PaymentTransaction) -> PaymentTransaction:
    """
    Pull latest status from provider and apply it to local transaction/order.
    Used as a fallback when webhook is delayed/unavailable.

    Guards:
      - State machine: only valid transitions are applied
      - Amount verification: mismatch blocks mark_paid
    """
    from apps.orders.services import mark_paid

    provider = registry.get(transaction.provider)
    if not transaction.provider_ref and transaction.provider != "cashfree":
        return transaction

    provider_ref = str(transaction.provider_ref or "").strip()
    if transaction.provider == "cashfree":
        raw = transaction.raw_response if isinstance(transaction.raw_response, dict) else {}
        # Cashfree status endpoint is keyed by merchant order_id in this integration.
        merchant_order_id = str(raw.get("order_id") or "").strip()
        cf_order_id = str(raw.get("cf_order_id") or "").strip()
        preferred_ref = merchant_order_id or provider_ref or cf_order_id
        if preferred_ref:
            provider_ref = preferred_ref
            if transaction.provider_ref != preferred_ref:
                transaction.provider_ref = preferred_ref
                transaction.save(update_fields=["provider_ref", "updated_at"])

    if not provider_ref:
        return transaction

    status_result = provider.get_status(provider_ref=provider_ref)
    if not status_result.success:
        logger.warning(
            "payment_reconcile_failed",
            transaction_id=str(transaction.id),
            provider=transaction.provider,
            error=status_result.error,
        )
        return transaction

    status_map = {
        "success": TransactionStatus.SUCCESS,
        "failed": TransactionStatus.FAILED,
        "pending": TransactionStatus.PENDING,
    }
    new_status = status_map.get(status_result.status, TransactionStatus.PENDING)

    # ── State machine guard ───────────────────────────────────
    allowed_success_from = {TransactionStatus.CREATED, TransactionStatus.PENDING, TransactionStatus.RETRY, TransactionStatus.FAILED}
    allowed_failed_from = {TransactionStatus.CREATED, TransactionStatus.PENDING, TransactionStatus.RETRY}

    if new_status == TransactionStatus.SUCCESS and transaction.status == TransactionStatus.SUCCESS:
        return transaction  # idempotent
    if new_status == TransactionStatus.SUCCESS and transaction.status not in allowed_success_from:
        logger.warning(
            "reconcile_invalid_transition",
            transaction_id=str(transaction.id),
            current_status=transaction.status,
            desired_status="success",
        )
        return transaction
    if new_status == TransactionStatus.FAILED and transaction.status not in allowed_failed_from:
        if transaction.status != TransactionStatus.FAILED:
            logger.warning(
                "reconcile_invalid_transition",
                transaction_id=str(transaction.id),
                current_status=transaction.status,
                desired_status="failed",
            )
        return transaction

    # ── Amount verification (on success) ──────────────────────
    if new_status == TransactionStatus.SUCCESS and status_result.amount is not None:
        try:
            provider_amount = Decimal(str(status_result.amount)).quantize(Decimal("0.01"))
            expected = transaction.total_amount.quantize(Decimal("0.01"))
            if provider_amount != expected:
                logger.warning(
                    "reconcile_amount_mismatch",
                    transaction_id=str(transaction.id),
                    order_id=str(transaction.order_id),
                    provider_amount=str(provider_amount),
                    expected_amount=str(expected),
                )
                return transaction
        except (InvalidOperation, ValueError, TypeError):
            logger.warning(
                "reconcile_amount_unparseable",
                transaction_id=str(transaction.id),
                raw_amount=str(status_result.amount),
            )
            return transaction

    transaction.status = new_status
    update_fields = ["status", "updated_at"]
    if isinstance(status_result.raw_response, dict) and status_result.raw_response:
        transaction.raw_response = status_result.raw_response
        update_fields.append("raw_response")
    if transaction.provider == "razorpay":
        if provider_ref.startswith("order_"):
            transaction.razorpay_order_id = provider_ref
        if status_result.provider_ref and status_result.provider_ref.startswith("pay_"):
            transaction.provider_ref = status_result.provider_ref
            transaction.razorpay_payment_id = status_result.provider_ref
            update_fields.extend(["provider_ref", "razorpay_payment_id"])
        elif provider_ref and provider_ref != transaction.provider_ref:
            transaction.provider_ref = provider_ref
            update_fields.append("provider_ref")
        if transaction.razorpay_order_id:
            update_fields.append("razorpay_order_id")
    transaction.save(update_fields=list(dict.fromkeys(update_fields)))

    if new_status == TransactionStatus.SUCCESS and transaction.order.status in ("placed", "draft"):
        mark_paid(
            order=transaction.order,
            payment_reference=str((transaction.raw_response or {}).get("cf_payment_id") or transaction.provider_ref or provider_ref),
            payment_method=transaction.provider,
        )

    return transaction


@transaction.atomic
def reconcile_order_payment(*, order) -> PaymentTransaction | None:
    txn = (
        PaymentTransaction.objects
        .filter(order=order)
        .exclude(provider__iexact="cod")
        .order_by("-created_at")
        .first()
    )
    if not txn:
        return None
    return reconcile_transaction_status(transaction=txn)


# ─────────────────────────────────────────────────────────────
#  3.  Retry Payment
# ─────────────────────────────────────────────────────────────

def retry_payment(*, transaction: PaymentTransaction, return_url: str = "") -> PaymentTransaction:
    """
    Re-initiate a payment for a failed transaction.
    Called by the Celery retry task with exponential backoff.

    Raises ValidationError if retry limit reached.
    """
    if not transaction.can_retry:
        raise ValidationError(
            f"Transaction {transaction.id} has reached its retry limit "
            f"({transaction.retry_count}/{transaction.max_retries})."
        )

    transaction.retry_count += 1
    transaction.status       = TransactionStatus.RETRY
    transaction.save(update_fields=["retry_count", "status", "updated_at"])

    logger.info(
        "payment_retry_attempt",
        transaction_id=str(transaction.id),
        attempt=transaction.retry_count,
    )

    # Re-initiate using same provider
    return initiate_payment(
        order=transaction.order,
        provider_name=transaction.provider,
        currency=transaction.currency,
        return_url=return_url,
        initiated_by=transaction.initiated_by,
    )


# ─────────────────────────────────────────────────────────────
#  4.  Refund
# ─────────────────────────────────────────────────────────────

def refund_payment(
    *,
    transaction: PaymentTransaction,
    amount: Decimal | None = None,
    reason: str = "",
    changed_by=None,
) -> dict:
    """
    Initiate a refund for a successful transaction.
    amount=None → full refund.
    """
    from .models import RefundSource
    from .refund_service import create_refund

    refund_amount = amount or transaction.remaining_refundable_amount
    refund = create_refund(
        order=transaction.order,
        payment=transaction,
        amount=refund_amount,
        source=RefundSource.MANUAL,
        reason=reason,
        metadata={"trigger": "manual_refund_api"},
        changed_by=changed_by,
    )
    success = refund.status == "success"
    return {
        "success": success,
        "refund_ref": refund.refund_id,
        "cf_refund_id": refund.cf_refund_id,
        "amount": str(refund.amount),
        "status": refund.status,
        "error": refund.metadata.get("provider_error", "") if isinstance(refund.metadata, dict) else "",
    }

