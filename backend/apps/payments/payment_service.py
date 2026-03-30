from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import transaction

from core.logging import get_logger

from apps.orders.models import OrderStatus
from apps.orders.services import mark_paid
from apps.payments.models import PaymentTransaction, TransactionStatus

logger = get_logger(__name__)

# ─────────────────────────────────────────────────────────────
#  Payment state machine: allowed transitions
# ─────────────────────────────────────────────────────────────
# pending/retry/failed → success  (delayed webhook can arrive after a retry)
_ALLOWED_SUCCESS_FROM = {
    TransactionStatus.PENDING,
    TransactionStatus.RETRY,
    TransactionStatus.FAILED,
}
# pending/retry → failed
_ALLOWED_FAILED_FROM = {
    TransactionStatus.PENDING,
    TransactionStatus.RETRY,
}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _resolve_transaction(*, provider_name: str, payment_data: dict[str, Any]) -> PaymentTransaction | None:
    cf_payment_id = _clean(
        payment_data.get("cf_payment_id")
        or payment_data.get("payment_id")
        or payment_data.get("paymentId")
    )
    cf_order_id = _clean(
        payment_data.get("cf_order_id")
        or payment_data.get("order_token")
        or payment_data.get("orderToken")
    )
    order_id = _clean(payment_data.get("order_id") or payment_data.get("orderId"))

    txn = None
    if cf_payment_id:
        txn = (
            PaymentTransaction.objects
            .filter(provider=provider_name, provider_ref=cf_payment_id)
            .order_by("-created_at")
            .first()
        )

    if txn is None and order_id:
        txn = (
            PaymentTransaction.objects
            .filter(provider=provider_name, order__id=order_id)
            .order_by("-created_at")
            .first()
        )
    if txn is None and cf_order_id:
        txn = (
            PaymentTransaction.objects
            .filter(provider=provider_name, provider_ref=cf_order_id)
            .order_by("-created_at")
            .first()
        )
    return txn


# ─────────────────────────────────────────────────────────────
#  Amount & currency verification
# ─────────────────────────────────────────────────────────────

def _verify_amount_and_currency(
    *, txn: PaymentTransaction, payment_data: dict[str, Any],
) -> tuple[bool, str]:
    """
    Compare provider-reported amount/currency with our transaction record.
    Returns (is_valid, reason).
    """
    # Extract provider-reported amount (try multiple field names)
    raw_amount = (
        payment_data.get("payment_amount")
        or payment_data.get("order_amount")
        or payment_data.get("amount")
    )
    if raw_amount is None:
        # Provider didn't include amount — can't verify, allow through
        # (some webhook formats omit amount on failure events)
        return True, ""

    try:
        provider_amount = Decimal(str(raw_amount)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError):
        return False, f"Unparseable provider amount: {raw_amount}"

    provider_currency = (
        _clean(
            payment_data.get("payment_currency")
            or payment_data.get("order_currency")
            or payment_data.get("currency")
        ).upper()
        or txn.currency
    )

    expected_amount = txn.total_amount.quantize(Decimal("0.01"))

    if provider_amount != expected_amount:
        return False, (
            f"Amount mismatch: provider={provider_amount}, expected={expected_amount}"
        )
    if provider_currency != txn.currency:
        return False, (
            f"Currency mismatch: provider={provider_currency}, expected={txn.currency}"
        )
    return True, ""


# ─────────────────────────────────────────────────────────────
#  Handle payment SUCCESS
# ─────────────────────────────────────────────────────────────

@transaction.atomic
def handle_payment_success(*, payment_data: dict[str, Any], provider_name: str = "cashfree") -> PaymentTransaction | None:
    """
    Mark a payment transaction as SUCCESS idempotently.

    Guards:
      - Idempotent: already SUCCESS → skip
      - State machine: only pending/retry/failed → success allowed
      - Amount/currency verification: mismatch → block, log suspicious
    """
    txn = _resolve_transaction(provider_name=provider_name, payment_data=payment_data)
    if txn is None:
        logger.warning("payment_success_transaction_not_found", provider=provider_name, payment_data=payment_data)
        return None

    # ── Idempotent: already succeeded ─────────────────────────
    if txn.status == TransactionStatus.SUCCESS:
        logger.info("payment_success_duplicate_skip", transaction_id=str(txn.id), provider=provider_name)
        return txn

    # ── State machine guard ───────────────────────────────────
    if txn.status not in _ALLOWED_SUCCESS_FROM:
        logger.warning(
            "payment_success_invalid_transition",
            transaction_id=str(txn.id),
            current_status=txn.status,
            provider=provider_name,
        )
        return txn

    # ── Amount & currency verification ────────────────────────
    amount_ok, mismatch_reason = _verify_amount_and_currency(txn=txn, payment_data=payment_data)
    if not amount_ok:
        logger.warning(
            "payment_amount_mismatch",
            transaction_id=str(txn.id),
            order_id=str(txn.order_id),
            provider=provider_name,
            mismatch_reason=mismatch_reason,
        )
        # Do NOT mark as success — keep in current state
        return txn

    # ── Apply success ─────────────────────────────────────────
    provider_ref = _clean(payment_data.get("cf_payment_id") or payment_data.get("payment_id"))
    txn.status = TransactionStatus.SUCCESS
    # For Cashfree, keep provider_ref as cf_order_id so status polling/refunds
    # continue to work against /orders/{cf_order_id} endpoints.
    if provider_name == "cashfree":
        raw = txn.raw_response if isinstance(txn.raw_response, dict) else {}
        if provider_ref:
            raw["cf_payment_id"] = provider_ref
        txn.raw_response = raw
        txn.save(update_fields=["status", "raw_response", "updated_at"])
    else:
        txn.provider_ref = provider_ref or txn.provider_ref
        txn.save(update_fields=["status", "provider_ref", "updated_at"])

    if txn.order.status in {OrderStatus.PLACED, OrderStatus.DRAFT}:
        mark_paid(
            order=txn.order,
            payment_reference=txn.provider_ref,
            payment_method=txn.provider,
        )

    logger.info(
        "payment_success_applied",
        provider=provider_name,
        transaction_id=str(txn.id),
        order_id=str(txn.order_id),
        provider_ref=txn.provider_ref,
    )
    return txn


# ─────────────────────────────────────────────────────────────
#  Handle payment FAILED
# ─────────────────────────────────────────────────────────────

@transaction.atomic
def handle_payment_failed(*, payment_data: dict[str, Any], provider_name: str = "cashfree") -> PaymentTransaction | None:
    """
    Mark a payment transaction as FAILED idempotently.

    Guards:
      - Idempotent: already FAILED → skip
      - State machine: only pending/retry → failed allowed
      - Releases stock reservations if order is still in placed/draft
    """
    txn = _resolve_transaction(provider_name=provider_name, payment_data=payment_data)
    if txn is None:
        logger.warning("payment_failed_transaction_not_found", provider=provider_name, payment_data=payment_data)
        return None

    # ── Idempotent: already failed ────────────────────────────
    if txn.status == TransactionStatus.FAILED:
        logger.info("payment_failed_duplicate_skip", transaction_id=str(txn.id), provider=provider_name)
        return txn

    # ── State machine guard ───────────────────────────────────
    if txn.status not in _ALLOWED_FAILED_FROM:
        logger.warning(
            "payment_failed_invalid_transition",
            transaction_id=str(txn.id),
            current_status=txn.status,
            provider=provider_name,
        )
        return txn

    txn.status = TransactionStatus.FAILED
    txn.save(update_fields=["status", "updated_at"])
    logger.warning(
        "payment_failed_applied",
        provider=provider_name,
        transaction_id=str(txn.id),
        order_id=str(txn.order_id),
    )

    # ── Release stock reservations if order hasn't progressed ─
    if txn.order.status in {OrderStatus.PLACED, OrderStatus.DRAFT}:
        try:
            from apps.inventory.services import release_reservation
            release_reservation(
                order_id=str(txn.order_id),
                notes="Stock released — payment failed.",
            )
            logger.info(
                "stock_released_on_payment_failure",
                order_id=str(txn.order_id),
                transaction_id=str(txn.id),
            )
        except Exception:
            logger.exception(
                "stock_release_failed_on_payment_failure",
                order_id=str(txn.order_id),
                transaction_id=str(txn.id),
            )

    return txn
