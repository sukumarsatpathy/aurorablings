"""
pos.expenses
~~~~~~~~~~~~

Money spent while trading: tea, auto fare, packing, stall rent.

Cash comes out of the drawer, so a cash expense needs an open shift and writes a
``pay_out`` cash movement against it in the same transaction — the shift's
expected cash then already accounts for it at close, with no change to how the
close is calculated. A UPI expense is recorded for the books only; the drawer is
not touched.

No approval limit: expenses are entered by admins. They are never edited or
deleted — a mistake is voided with a reason, and a voided cash expense puts the
money back into the drawer total with a matching ``pay_in``.
"""

from __future__ import annotations

from decimal import Decimal

import structlog
from django.db import transaction
from django.utils import timezone

from apps.pos import services
from apps.pos.models import (
    CashMovementType,
    ExpensePaymentMode,
    POSExpense,
    POSShift,
)

logger = structlog.get_logger(__name__)

ZERO = Decimal("0.00")


class ExpenseError(Exception):
    """Raised when an expense cannot be recorded or voided as asked."""


def _store_bill(expense: POSExpense, upload) -> None:
    if not upload:
        return
    try:
        from core.image_optimization import compress_image

        filename, content = compress_image(
            upload, output_dir="", max_width=1600, quality=78, file_stem=f"bill-{expense.id.hex[:12]}",
        )
        expense.bill_image.save(filename, content, save=False)
    except Exception:  # keep the original rather than lose the bill
        logger.warning("pos_expense_bill_compress_failed", expense_id=str(expense.id), exc_info=True)
        if hasattr(upload, "seek"):
            upload.seek(0)
        expense.bill_image.save(getattr(upload, "name", "bill.jpg"), upload, save=False)


@transaction.atomic
def record_expense(
    *,
    payment_mode: str,
    amount,
    remarks: str,
    staff,
    shift: POSShift | None = None,
    bill_image=None,
    upi_reference: str = "",
) -> POSExpense:
    if payment_mode not in ExpensePaymentMode.values:
        raise ExpenseError("Payment mode must be cash or UPI.")
    try:
        amount = Decimal(str(amount)).quantize(Decimal("0.01"))
    except Exception:
        raise ExpenseError("Amount must be a number.")
    if amount <= ZERO:
        raise ExpenseError("Amount must be more than zero.")
    remarks = (remarks or "").strip()
    if not remarks:
        raise ExpenseError("Add a remark — what was the money for?")

    if shift is not None:
        shift = POSShift.objects.select_for_update().get(pk=shift.pk)

    movement = None
    if payment_mode == ExpensePaymentMode.CASH:
        if shift is None or not shift.is_open:
            raise ExpenseError("A cash expense comes out of the drawer, so it needs an open shift.")
        movement = services.record_cash_movement(
            shift=shift,
            movement_type=CashMovementType.PAY_OUT,
            amount=amount,
            reason=f"Expense: {remarks}"[:255],
            staff=staff,
        )
    elif shift is not None and not shift.is_open:
        # A UPI expense may be tagged to a shift for reporting, but not a closed one.
        shift = None

    expense = POSExpense(
        payment_mode=payment_mode,
        amount=amount,
        remarks=remarks,
        upi_reference=(upi_reference or "").strip() if payment_mode == ExpensePaymentMode.UPI else "",
        shift=shift,
        cash_movement=movement,
        created_by=staff,
    )
    _store_bill(expense, bill_image)
    expense.save()

    logger.info(
        "pos_expense_recorded",
        expense_id=str(expense.id), mode=payment_mode, amount=str(amount),
        shift_id=str(shift.id) if shift else None, staff=getattr(staff, "id", None),
    )
    return expense


@transaction.atomic
def void_expense(*, expense: POSExpense, staff, reason: str) -> POSExpense:
    expense = POSExpense.objects.select_for_update().get(pk=expense.pk)
    reason = (reason or "").strip()
    if not reason:
        raise ExpenseError("Give a reason for voiding the expense.")
    if expense.is_voided:
        raise ExpenseError("This expense is already voided.")

    movement = None
    if expense.payment_mode == ExpensePaymentMode.CASH and expense.cash_movement_id:
        shift = expense.shift
        if shift is None or not shift.is_open:
            raise ExpenseError(
                "That shift is closed and its drawer already counted, so this cash "
                "expense can't be voided. Record a correction on the current shift instead."
            )
        movement = services.record_cash_movement(
            shift=shift,
            movement_type=CashMovementType.PAY_IN,
            amount=expense.amount,
            reason=f"Expense voided: {reason}"[:255],
            staff=staff,
        )

    expense.voided_at = timezone.now()
    expense.voided_by = staff
    expense.void_reason = reason
    expense.void_movement = movement
    expense.save(update_fields=["voided_at", "voided_by", "void_reason", "void_movement"])
    logger.info("pos_expense_voided", expense_id=str(expense.id), staff=getattr(staff, "id", None))
    return expense


def expense_totals(qs) -> dict:
    """Totals of live (not voided) expenses, by payment mode."""
    from django.db.models import Count, Sum

    live = qs.filter(voided_at__isnull=True)
    out = {"cash": "0.00", "upi": "0.00", "total": "0.00", "count": 0}
    grand = ZERO
    count = 0
    for row in live.values("payment_mode").annotate(total=Sum("amount"), n=Count("id")):
        value = (row["total"] or ZERO).quantize(Decimal("0.01"))
        out[row["payment_mode"]] = str(value)
        grand += value
        count += row["n"]
    out["total"] = str(grand.quantize(Decimal("0.01")))
    out["count"] = count
    return out
