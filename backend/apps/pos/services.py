"""
pos.services
~~~~~~~~~~~~

Shift lifecycle and the cash tender.

The one rule worth stating plainly: cash at the counter is only ever recorded
through :func:`take_cash_tender`, which writes into the payments tender ledger
*and* attaches the tender to the open shift.  Anything that records cash without
a shift is money that cannot be reconciled at close, which is the whole failure
mode a POS exists to prevent.
"""

from __future__ import annotations

from decimal import Decimal

import structlog
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from apps.orders.models import Order, PaymentStatus, SalesChannel
from apps.payments import tender_service
from apps.payments.models import TenderMethod, TenderStatus
from apps.pos.models import (
    CashMovementType,
    POSCashMovement,
    POSShift,
    POSTerminal,
    ShiftStatus,
)

logger = structlog.get_logger(__name__)

ZERO = Decimal("0.00")


class ShiftError(Exception):
    """Raised when a shift operation would leave the drawer unaccountable."""


# ─────────────────────────────────────────────────────────────
#  Shift lifecycle
# ─────────────────────────────────────────────────────────────

@transaction.atomic
def open_shift(*, terminal: POSTerminal, staff, opening_float: Decimal = ZERO) -> POSShift:
    """Start trading on a terminal with a counted float."""
    if opening_float < ZERO:
        raise ShiftError("Opening float cannot be negative.")

    if POSShift.objects.filter(terminal=terminal, status=ShiftStatus.OPEN).exists():
        raise ShiftError(
            f"Terminal {terminal.code} already has an open shift. Close it before opening another."
        )

    shift = POSShift.objects.create(
        terminal=terminal,
        opened_by=staff,
        opening_float=Decimal(opening_float).quantize(Decimal("0.01")),
    )
    logger.info("pos_shift_opened", shift_id=str(shift.id), terminal=terminal.code,
                staff=getattr(staff, "id", None), opening_float=str(opening_float))
    return shift


def cash_taken(shift: POSShift) -> Decimal:
    """Cash collected as sales during this shift. Voided tenders don't count."""
    total = shift.tenders.filter(
        method=TenderMethod.CASH, status=TenderStatus.CAPTURED,
    ).aggregate(total=Sum("amount_applied"))["total"]
    return (total or ZERO).quantize(Decimal("0.01"))


def cash_movements_net(shift: POSShift) -> Decimal:
    """Pay-ins minus pay-outs and cash refunds."""
    net = ZERO
    for movement in shift.cash_movements.all():
        net += movement.signed_amount
    return net.quantize(Decimal("0.01"))


def expected_cash(shift: POSShift) -> Decimal:
    """
    What should physically be in the drawer right now.

    Derived from the ledger every time it is asked for, never stored as a running
    total — a counter that drifts is worse than no counter.
    """
    return (shift.opening_float + cash_taken(shift) + cash_movements_net(shift)).quantize(Decimal("0.01"))


def open_part_paid_orders(shift: POSShift):
    """
    Sales on this shift that hold real cash but were never completed.

    These are the reason a shift close can be wrong while every individual number
    looks right, so the close surfaces them rather than silently absorbing them.
    """
    return Order.objects.filter(
        Q(pos_shift=shift) & Q(payment_status=PaymentStatus.PARTIALLY_PAID)
    )


@transaction.atomic
def close_shift(
    *,
    shift: POSShift,
    staff,
    counted_cash: Decimal,
    note: str = "",
    force: bool = False,
) -> POSShift:
    """
    Count the drawer and close.

    Refuses while part-paid orders are open unless ``force`` is passed, because
    that is exactly when unmatched cash hides.  Forcing is allowed — a stall has
    to be able to pack up — but it is recorded in the close note.
    """
    if not shift.is_open:
        raise ShiftError("This shift is already closed.")

    outstanding = list(open_part_paid_orders(shift))
    if outstanding and not force:
        numbers = ", ".join(o.order_number for o in outstanding[:5])
        raise ShiftError(
            f"{len(outstanding)} part-paid order(s) still open on this shift ({numbers}). "
            "Settle or void them, or close with force=true to record it as-is."
        )

    expected = expected_cash(shift)
    counted = Decimal(counted_cash).quantize(Decimal("0.01"))

    shift.status = ShiftStatus.CLOSED
    shift.closed_by = staff
    shift.closed_at = timezone.now()
    shift.counted_cash = counted
    shift.expected_cash = expected
    shift.variance = (counted - expected).quantize(Decimal("0.01"))
    shift.close_note = note or (
        f"Forced close with {len(outstanding)} part-paid order(s) open." if outstanding else ""
    )
    shift.save(update_fields=[
        "status", "closed_by", "closed_at", "counted_cash",
        "expected_cash", "variance", "close_note",
    ])

    logger.info(
        "pos_shift_closed",
        shift_id=str(shift.id), terminal=shift.terminal.code,
        expected=str(expected), counted=str(counted), variance=str(shift.variance),
        part_paid_open=len(outstanding),
    )
    return shift


@transaction.atomic
def record_cash_movement(
    *,
    shift: POSShift,
    movement_type: str,
    amount: Decimal,
    reason: str,
    staff=None,
    order=None,
) -> POSCashMovement:
    """Money in or out of the drawer for a reason that is not a sale."""
    if not shift.is_open:
        raise ShiftError("Cannot move cash on a closed shift.")

    amount = Decimal(amount).quantize(Decimal("0.01"))
    if amount <= ZERO:
        raise ShiftError("Cash movement amount must be positive; the type carries the direction.")
    if not reason:
        raise ShiftError("A cash movement needs a reason — an unexplained drawer change is the thing being prevented.")

    movement = POSCashMovement.objects.create(
        shift=shift, movement_type=movement_type, amount=amount,
        reason=reason, created_by=staff, order=order,
    )
    logger.info("pos_cash_movement", shift_id=str(shift.id), type=movement_type,
                amount=str(amount), reason=reason)
    return movement


# ─────────────────────────────────────────────────────────────
#  Cash tender
# ─────────────────────────────────────────────────────────────

@transaction.atomic
def take_cash_tender(
    *,
    order: Order,
    shift: POSShift,
    staff,
    amount_applied: Decimal,
    cash_received: Decimal | None = None,
):
    """
    Take cash at the counter for one leg of a sale.

    ``amount_applied`` is what the sale is credited with; ``cash_received`` is
    what the customer physically handed over.  The difference is change — a
    drawer movement, never revenue.  Both are stored, because a shift that only
    knows the applied figure cannot be counted.
    """
    if not shift.is_open:
        raise ShiftError("Cannot take cash against a closed shift.")

    tender = tender_service.record_tender(
        order=order,
        method=TenderMethod.CASH,
        amount_applied=amount_applied,
        cash_received=cash_received,
        collected_by=staff,
        shift=shift,
        payment_method="cash",
    )
    return tender


@transaction.atomic
def void_cash_tender(*, tender, staff, reason: str = "sale voided"):
    """
    Take a cash leg back out: the ledger entry is voided and the physical refund
    is recorded against the shift, so the drawer still counts.
    """
    if tender.method != TenderMethod.CASH:
        raise ShiftError("Only cash tenders are voided this way; gateway legs are refunded.")
    if tender.status != TenderStatus.CAPTURED:
        raise ShiftError("This tender is not captured.")

    shift = tender.shift
    tender_service.void_tender(tender=tender, reason=reason, changed_by=staff)

    # No POSCashMovement row is written here on purpose. Voiding already removes
    # the tender from cash_taken(), which lowers expected_cash by exactly the
    # refunded amount; adding a movement as well would deduct it twice and leave
    # every forced close looking long.
    if shift:
        logger.info("pos_cash_tender_voided", tender_id=str(tender.id), shift_id=str(shift.id))
    return tender


# ─────────────────────────────────────────────────────────────
#  Voiding a part-paid sale
# ─────────────────────────────────────────────────────────────

@transaction.atomic
def void_sale(*, order: Order, staff, reason: str) -> Order:
    """
    Abandon a counter sale that already holds money.

    The scenario is ordinary: cash was taken, the customer changed their mind or
    walked off before the QR was paid, and the sale has to go away. What must not
    happen is the money going away quietly with it — so every cash leg is voided
    explicitly, which is what pulls it back out of the shift's expected drawer
    total, and the stock is released by the existing cancel path.

    Gateway legs are deliberately *not* voided here. Money that reached Razorpay
    comes back through the refund API, not by editing a row; a captured gateway
    tender makes this refuse and points at the refund flow instead.
    """
    if not reason:
        raise ShiftError("A void needs a reason. An unexplained reversal is what this prevents.")

    captured = order.tenders.filter(status=TenderStatus.CAPTURED)
    gateway_legs = captured.exclude(method=TenderMethod.CASH)
    if gateway_legs.exists():
        raise ShiftError(
            "This sale has a settled gateway payment. Refund it through the refund "
            "flow rather than voiding — the money is with Razorpay, not in the drawer."
        )

    refunded = ZERO
    for tender in captured.filter(method=TenderMethod.CASH):
        tender_service.void_tender(tender=tender, reason=f"sale voided: {reason}", changed_by=staff)
        refunded += tender.amount_applied

    order.refresh_from_db()

    from apps.orders.services import cancel_order
    cancel_order(order=order, changed_by=staff, reason=f"POS void: {reason}")

    order.refresh_from_db()
    logger.info(
        "pos_sale_voided",
        order_id=str(order.id), order_number=order.order_number,
        cash_refunded=str(refunded), reason=reason,
        staff=getattr(staff, "id", None),
    )
    return order


def part_paid_orders(*, terminal=None, shift=None):
    """
    Every counter sale holding money that was never completed.

    This is the list that belongs on the counter screen permanently. An order with
    cash against it and no second leg is the one thing that must not be forgotten
    at closing time, and nothing else in the system will raise its hand about it.
    """
    qs = Order.objects.filter(
        payment_status=PaymentStatus.PARTIALLY_PAID,
        channel=SalesChannel.POS,
    ).select_related("pos_terminal", "pos_shift").order_by("-created_at")

    if shift is not None:
        qs = qs.filter(pos_shift=shift)
    elif terminal is not None:
        qs = qs.filter(pos_terminal=terminal)
    return qs
