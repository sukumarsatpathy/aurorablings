"""
payments.tender_service
~~~~~~~~~~~~~~~~~~~~~~~

The settlement ledger.  Every rupee that reaches us for an order — online, at the
counter, in cash, or by UPI QR — is recorded here as an :class:`OrderTender`, and
the order's ``payment_status`` is derived from the ledger rather than set by hand.

Why a ledger rather than a column: split payment.  A counter sale of Rs 4,798 can
be Rs 2,000 cash plus Rs 2,798 by UPI QR.  With one payment column that sale is
unrepresentable; with a ledger it is two rows, the cash drawer reconciles against
cash rows, and the Razorpay settlement reconciles against gateway rows, without
either double-counting the other.

Invariants enforced here:
  1. Captured tenders never sum to more than ``order.grand_total``.
  2. Cash: ``cash_received - change_given == amount_applied``.  Change is a drawer
     movement, not revenue.
  3. Gateway tenders are idempotent on ``(provider, provider_ref)`` — webhook
     redelivery updates nothing and creates nothing.
  4. ``payment_status`` is only ever computed from the ledger.
"""

from __future__ import annotations

from decimal import Decimal

import structlog
from django.db import IntegrityError, transaction

from apps.orders.models import Order, PaymentStatus
from apps.payments.models import OrderTender, TenderMethod, TenderStatus

logger = structlog.get_logger(__name__)

ZERO = Decimal("0.00")

#: Tenders in these states count toward the order balance.
SETTLED_STATUSES = (TenderStatus.CAPTURED,)


class TenderError(Exception):
    """Raised when a tender would violate a ledger invariant."""


# ─────────────────────────────────────────────────────────────
#  Reads
# ─────────────────────────────────────────────────────────────

def amount_paid(order: Order) -> Decimal:
    """Sum of settled tenders for this order."""
    total = ZERO
    for tender in order.tenders.filter(status__in=SETTLED_STATUSES):
        total += tender.amount_applied
    return total.quantize(Decimal("0.01"))


def balance_due(order: Order) -> Decimal:
    """What is still to be collected.  Never negative."""
    due = (order.grand_total or ZERO) - amount_paid(order)
    return due if due > ZERO else ZERO


def derive_payment_status(order: Order) -> str:
    """
    The order's payment status *as the ledger sees it*.

    Refund states are owned by the refund flow, not by this function — an order
    that has been refunded keeps that status regardless of what was tendered.
    """
    if order.payment_status in (PaymentStatus.REFUNDED, PaymentStatus.PARTIALLY_REFUNDED):
        return order.payment_status

    paid = amount_paid(order)
    total = order.grand_total or ZERO

    if paid <= ZERO:
        return order.payment_status if order.payment_status == PaymentStatus.FAILED else PaymentStatus.PENDING
    if paid >= total:
        return PaymentStatus.PAID
    return PaymentStatus.PARTIALLY_PAID


# ─────────────────────────────────────────────────────────────
#  Writes
# ─────────────────────────────────────────────────────────────

@transaction.atomic
def record_tender(
    *,
    order: Order,
    method: str,
    amount_applied: Decimal,
    status: str = TenderStatus.CAPTURED,
    cash_received: Decimal | None = None,
    change_given: Decimal | None = None,
    provider: str = "",
    provider_ref: str = "",
    payment_transaction=None,
    collected_by=None,
    notes: str = "",
    raw: dict | None = None,
) -> OrderTender:
    """
    Add one leg of payment to an order and re-derive its payment status.

    Locks the order row, so two tills (or a webhook racing a counter) cannot both
    believe they are collecting the last rupee.

    Idempotent for gateway legs: recording a tender whose ``(provider,
    provider_ref)`` already exists returns the existing row untouched.  Razorpay
    retries webhooks, so this is load-bearing, not defensive decoration.

    :raises TenderError: if the tender would over-collect, or if the cash
        arithmetic does not balance.
    """
    amount_applied = Decimal(amount_applied).quantize(Decimal("0.01"))

    if amount_applied == ZERO:
        raise TenderError("A tender cannot be for zero.")

    # Re-read under a row lock so the balance we check is the balance we commit against.
    locked = Order.objects.select_for_update().get(pk=order.pk)

    if provider_ref:
        existing = OrderTender.objects.filter(provider=provider, provider_ref=provider_ref).first()
        if existing is not None:
            logger.info(
                "tender_duplicate_ignored",
                order_id=str(locked.id),
                provider=provider,
                provider_ref=provider_ref,
                tender_id=str(existing.id),
            )
            return existing

    if status in SETTLED_STATUSES and amount_applied > ZERO:
        outstanding = balance_due(locked)
        if amount_applied > outstanding:
            raise TenderError(
                f"Tender of {amount_applied} exceeds the outstanding balance of "
                f"{outstanding} on order {locked.order_number}."
            )

    if method == TenderMethod.CASH:
        received = Decimal(cash_received if cash_received is not None else amount_applied)
        change = Decimal(change_given if change_given is not None else (received - amount_applied))
        if change < ZERO:
            raise TenderError("Cash received is less than the amount applied.")
        if (received - change) != amount_applied:
            raise TenderError(
                f"Cash does not balance: received {received} - change {change} "
                f"!= applied {amount_applied}."
            )
        cash_received, change_given = received, change
    else:
        cash_received, change_given = None, None

    try:
        tender = OrderTender.objects.create(
            order=locked,
            method=method,
            status=status,
            amount_applied=amount_applied,
            currency=locked.currency or "INR",
            cash_received=cash_received,
            change_given=change_given,
            provider=provider,
            provider_ref=provider_ref,
            transaction=payment_transaction,
            collected_by=collected_by,
            notes=notes,
            raw=raw or {},
        )
    except IntegrityError:
        # Lost a race against a concurrent webhook delivery for the same payment.
        existing = OrderTender.objects.filter(provider=provider, provider_ref=provider_ref).first()
        if existing is not None:
            return existing
        raise

    logger.info(
        "tender_recorded",
        order_id=str(locked.id),
        order_number=locked.order_number,
        method=method,
        amount=str(amount_applied),
        status=status,
        collected_by=getattr(collected_by, "id", None),
    )

    sync_payment_status(order=locked, changed_by=collected_by, payment_reference=provider_ref)
    order.refresh_from_db()
    return tender


@transaction.atomic
def void_tender(*, tender: OrderTender, reason: str = "", changed_by=None) -> OrderTender:
    """
    Take one leg back out of the ledger.

    Used when a part-paid counter sale is abandoned: the cash leg is voided and
    the money physically leaves the drawer, so the shift still balances.
    """
    tender.status = TenderStatus.VOIDED
    tender.notes = (tender.notes + " | " if tender.notes else "") + (reason or "voided")
    tender.save(update_fields=["status", "notes", "updated_at"])

    logger.info("tender_voided", tender_id=str(tender.id), order_id=str(tender.order_id), reason=reason)
    sync_payment_status(order=tender.order, changed_by=changed_by)
    return tender


def sync_payment_status(*, order: Order, changed_by=None, payment_reference: str = "") -> Order:
    """
    Re-derive ``payment_status`` from the ledger and, on full settlement, run the
    existing ``orders.services.mark_paid`` side effects exactly once.

    Imported lazily: ``orders.services`` imports from payments, so a module-level
    import here would be circular.
    """
    from apps.orders import services as order_services

    new_status = derive_payment_status(order)

    if new_status == PaymentStatus.PAID and order.payment_status != PaymentStatus.PAID:
        order_services.mark_paid(
            order=order,
            payment_reference=payment_reference or order.payment_reference or "",
            changed_by=changed_by,
        )
        return order

    if new_status != order.payment_status:
        order.payment_status = new_status
        order.save(update_fields=["payment_status"])

    return order
