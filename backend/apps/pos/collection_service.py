"""
pos.collection_service
~~~~~~~~~~~~~~~~~~~~~~

Raising a UPI collection at the counter and telling the till whether it's been
paid yet.

Two rules shape everything here:

1. **The QR is always for the balance, never the order total.** On a split sale
   the customer has already handed over cash; a QR for the full amount would
   charge them twice. ``balance_due`` is asked of the ledger at the moment the QR
   is created, never passed in by the tablet.

2. **The counter never decides a payment happened.** It polls *our* backend, and
   our backend only believes the verified webhook. The status endpoint here reads
   the tender ledger — it does not call Razorpay to find out whether a customer
   paid, because a screen that can be talked into saying "PAID" by anything other
   than a signed webhook is the whole problem.
"""

from __future__ import annotations

from decimal import Decimal

import structlog
from django.db import transaction

from apps.orders.models import Order
from apps.payments import tender_service
from apps.payments.models import PaymentTransaction, TransactionStatus
from apps.payments.providers.registry import registry

logger = structlog.get_logger(__name__)

ZERO = Decimal("0.00")
PROVIDER = "razorpay"


class CollectionError(Exception):
    """Raised when a UPI collection cannot be raised for this order."""


@transaction.atomic
def create_upi_collection(
    *,
    order: Order,
    staff=None,
    close_by_minutes: int = 15,
) -> dict:
    """
    Raise a dynamic QR for whatever is still owed on this order.

    Falls back to a Razorpay payment link if the QR Codes API is unavailable on
    the account — the counter can render a link as a QR itself, so a merchant
    whose account lacks the QR product still gets a working till rather than a
    dead button. The response says which one came back so the UI can label it.
    """
    outstanding = tender_service.balance_due(order)
    if outstanding <= ZERO:
        raise CollectionError("This order is already fully paid.")

    try:
        provider = registry.get(PROVIDER)
    except KeyError as exc:
        raise CollectionError(str(exc)) from exc

    txn = PaymentTransaction.objects.create(
        order=order,
        provider=PROVIDER,
        status=TransactionStatus.CREATED,
        amount=outstanding,
        total_amount=outstanding,
        currency=order.currency or "INR",
        initiated_by=staff,
    )

    metadata = {
        "channel": "pos",
        "transaction_id": str(txn.id),
        "terminal": order.pos_terminal.code if order.pos_terminal_id else "",
    }

    try:
        result = provider.create_qr_code(
            order_id=str(order.id),
            amount=outstanding,
            currency=order.currency or "INR",
            close_by_minutes=close_by_minutes,
            metadata=metadata,
        )
    except NotImplementedError:
        result = None

    if result is not None and result.success:
        txn.provider_ref = result.provider_ref
        txn.status = TransactionStatus.PENDING
        txn.raw_response = result.raw or {}
        txn.payment_url = result.image_url
        txn.save(update_fields=["provider_ref", "status", "raw_response", "payment_url", "updated_at"])

        logger.info(
            "pos_qr_created", order_id=str(order.id), qr_id=result.provider_ref,
            amount=str(outstanding),
        )
        return {
            "kind": "qr",
            "transaction_id": str(txn.id),
            "qr_id": result.provider_ref,
            "image_url": result.image_url,
            "amount": str(outstanding),
            "close_by": result.close_by,
        }

    qr_error = result.error if result is not None else "provider has no QR support"
    logger.warning("pos_qr_unavailable_falling_back", order_id=str(order.id), error=qr_error)

    link = provider.initiate(
        order_id=str(order.id),
        amount=outstanding,
        currency=order.currency or "INR",
        customer_email=order.guest_email or "",
        customer_name=order.contact_name or "Customer",
        customer_phone=order.contact_phone or "",
        metadata=metadata,
    )
    if not link.success:
        txn.status = TransactionStatus.FAILED
        txn.last_error = f"QR: {qr_error} | Link: {link.error}"
        txn.save(update_fields=["status", "last_error", "updated_at"])
        raise CollectionError(
            f"Could not raise a UPI collection. QR: {qr_error}. Payment link: {link.error}"
        )

    txn.provider_ref = link.provider_ref
    txn.status = TransactionStatus.PENDING
    txn.payment_url = getattr(link, "payment_url", "") or ""
    txn.save(update_fields=["provider_ref", "status", "payment_url", "updated_at"])

    return {
        "kind": "link",
        "transaction_id": str(txn.id),
        "qr_id": link.provider_ref,
        "payment_url": txn.payment_url,
        "amount": str(outstanding),
        "note": "QR codes unavailable on this account — render this link as a QR.",
        "qr_error": qr_error,
    }


def cancel_collection(*, transaction_id: str) -> bool:
    """
    Close an outstanding QR.

    Called before regenerating, so an expired QR and its replacement can never
    both be paid — which would over-collect and leave you refunding a customer
    who did nothing wrong.
    """
    txn = PaymentTransaction.objects.filter(pk=transaction_id).first()
    if not txn or not txn.provider_ref:
        return False

    try:
        provider = registry.get(txn.provider)
    except KeyError:
        return False

    try:
        closed = provider.close_qr_code(provider_ref=txn.provider_ref)
    except NotImplementedError:
        closed = False

    if txn.status in (TransactionStatus.CREATED, TransactionStatus.PENDING):
        txn.status = TransactionStatus.CANCELLED
        txn.save(update_fields=["status", "updated_at"])

    logger.info("pos_collection_cancelled", transaction_id=str(txn.id), closed_upstream=closed)
    return closed


def payment_state(*, order: Order) -> dict:
    """
    What the counter polls.

    Reads the ledger only. If this ever starts asking Razorpay directly, a slow or
    lying response becomes a "PAID" on the till, which is exactly the failure the
    webhook-is-authoritative rule exists to prevent.
    """
    order.refresh_from_db()
    return {
        "order_number": order.order_number,
        "payment_status": order.payment_status,
        "grand_total": str(order.grand_total),
        "amount_paid": str(tender_service.amount_paid(order)),
        "balance_due": str(tender_service.balance_due(order)),
        "tenders": [
            {
                "method": t.method,
                "amount": str(t.amount_applied),
                "status": t.status,
                "at": t.created_at,
            }
            for t in order.tenders.all()
        ],
    }
