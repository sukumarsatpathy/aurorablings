"""
pos.models
~~~~~~~~~~

Terminals, shifts and cash movements.

The shift is the piece people skip and then regret.  Without it, "we took about
forty thousand at the Bhubaneswar exhibition" is a feeling; with it, it is a
number with an opening float, a counted close and a recorded variance, per
terminal, per day, per person.
"""

import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _


class POSTerminal(models.Model):
    """A counter. A stall table, a shop till, a staff member's phone."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(
        max_length=32, unique=True,
        help_text="Short identifier printed on receipts, e.g. STALL-01.",
    )
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=150, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("POS terminal")
        verbose_name_plural = _("POS terminals")
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} — {self.name}"


class ShiftStatus(models.TextChoices):
    OPEN   = "open",   _("Open")
    CLOSED = "closed", _("Closed")


class POSShift(models.Model):
    """
    One person, one terminal, one stretch of trading, one drawer.

    ``expected_cash`` is not stored as a running total — it is derived from the
    cash tenders and cash movements attached to the shift, so it cannot drift
    away from the ledger.  It is snapshotted onto the row only at close, as the
    record of what was expected at that moment.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    terminal = models.ForeignKey(POSTerminal, on_delete=models.PROTECT, related_name="shifts")
    status = models.CharField(
        max_length=10, choices=ShiftStatus.choices,
        default=ShiftStatus.OPEN, db_index=True,
    )

    opened_by = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT, related_name="pos_shifts_opened",
    )
    opened_at = models.DateTimeField(auto_now_add=True, db_index=True)
    opening_float = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text="Cash counted into the drawer at open.",
    )

    closed_by = models.ForeignKey(
        "accounts.User", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="pos_shifts_closed",
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    counted_cash = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    expected_cash = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    variance = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="counted - expected. Negative is short.",
    )
    close_note = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = _("POS shift")
        verbose_name_plural = _("POS shifts")
        ordering = ["-opened_at"]
        constraints = [
            # Two open shifts on one terminal means two people counting the same
            # drawer. The database refuses rather than trusting the UI.
            models.UniqueConstraint(
                fields=["terminal"],
                condition=models.Q(status="open"),
                name="uniq_open_shift_per_terminal",
            ),
        ]

    def __str__(self):
        return f"Shift {self.terminal.code} {self.opened_at:%Y-%m-%d %H:%M} ({self.status})"

    @property
    def is_open(self) -> bool:
        return self.status == ShiftStatus.OPEN


class CashMovementType(models.TextChoices):
    PAY_IN  = "pay_in",  _("Pay in")
    PAY_OUT = "pay_out", _("Pay out")
    REFUND  = "refund",  _("Cash refund to customer")


class POSCashMovement(models.Model):
    """
    Cash entering or leaving the drawer for a reason that is not a sale.

    A cash refund on a voided part-paid sale is the case that matters: the money
    physically leaves, and without a row here the shift closes short and nobody
    can say why.  ``amount`` is always positive; the type carries the direction.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shift = models.ForeignKey(POSShift, on_delete=models.CASCADE, related_name="cash_movements")
    movement_type = models.CharField(max_length=20, choices=CashMovementType.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.CharField(max_length=255)
    order = models.ForeignKey(
        "orders.Order", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="pos_cash_movements",
    )
    created_by = models.ForeignKey(
        "accounts.User", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="pos_cash_movements",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("POS cash movement")
        verbose_name_plural = _("POS cash movements")
        ordering = ["created_at"]
        constraints = [
            models.CheckConstraint(check=models.Q(amount__gt=0), name="cash_movement_amount_positive"),
        ]

    def __str__(self):
        return f"{self.movement_type} {self.amount} ({self.reason})"

    @property
    def signed_amount(self):
        """Positive if it adds to the drawer, negative if it takes from it."""
        return self.amount if self.movement_type == CashMovementType.PAY_IN else -self.amount


# ─────────────────────────────────────────────────────────────
#  Quick items — pieces sold at the counter without a catalogue entry
# ─────────────────────────────────────────────────────────────

class POSQuickItem(models.Model):
    """
    A piece with no barcode and no product page, photographed at the counter.

    Deliberately *not* a catalogue Product: these never reach the website, the
    product admin, the sitemap or the label printer. They exist only so the till
    can sell them with a picture on the bill and a stock count that goes down.

    The price lives here, on the server. A sale line names the quick item and a
    quantity — the tablet still never sends a price.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150)
    image = models.ImageField(upload_to="pos/quick-items/%Y/%m/", blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    #: Pieces on hand. Goes down when a sale is rung up, back up when it is voided.
    quantity = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True, db_index=True)
    created_by = models.ForeignKey(
        "accounts.User", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="pos_quick_items",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("POS quick item")
        verbose_name_plural = _("POS quick items")
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(check=models.Q(price__gt=0), name="pos_quick_item_price_positive"),
        ]

    def __str__(self):
        return f"{self.name} — ₹{self.price} ({self.quantity} left)"


class POSQuickSaleLine(models.Model):
    """
    Which order line was a quick item, and whether its stock has been put back.

    Kept here rather than as a column on OrderItem so the orders app is untouched:
    the order line itself is an ordinary OrderItem with no variant, which every
    order, invoice and email path already handles (it is the same shape as a
    line whose product was later deleted).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        "orders.Order", on_delete=models.CASCADE, related_name="pos_quick_lines",
    )
    order_item = models.OneToOneField(
        "orders.OrderItem", on_delete=models.CASCADE, related_name="pos_quick_line",
    )
    quick_item = models.ForeignKey(
        POSQuickItem, on_delete=models.PROTECT, related_name="sale_lines",
    )
    quantity = models.PositiveIntegerField()
    #: Set once the pieces have gone back on the shelf — makes restocking idempotent.
    restocked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("POS quick sale line")
        verbose_name_plural = _("POS quick sale lines")
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.quick_item.name} × {self.quantity}"


# ─────────────────────────────────────────────────────────────
#  Expenses
# ─────────────────────────────────────────────────────────────

class ExpensePaymentMode(models.TextChoices):
    CASH = "cash", _("Cash")
    UPI  = "upi",  _("UPI")


class POSExpense(models.Model):
    """
    Money spent on running the shop or stall — tea, transport, packing, rent.

    Cash expenses come out of the drawer, so each writes a ``pay_out`` cash
    movement on the open shift and the close still balances. UPI expenses are
    recorded for the books and leave the drawer alone.

    Never edited or deleted: a mistake is voided, which (for cash) puts the money
    back into the drawer total with a matching ``pay_in``.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment_mode = models.CharField(max_length=10, choices=ExpensePaymentMode.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    remarks = models.CharField(max_length=500)
    bill_image = models.ImageField(upload_to="pos/expense-bills/%Y/%m/", blank=True)
    upi_reference = models.CharField(max_length=64, blank=True)
    shift = models.ForeignKey(
        POSShift, null=True, blank=True,
        on_delete=models.PROTECT, related_name="expenses",
    )
    cash_movement = models.OneToOneField(
        POSCashMovement, null=True, blank=True,
        on_delete=models.PROTECT, related_name="expense",
    )
    created_by = models.ForeignKey(
        "accounts.User", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="pos_expenses",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    voided_at = models.DateTimeField(null=True, blank=True)
    voided_by = models.ForeignKey(
        "accounts.User", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="pos_expenses_voided",
    )
    void_reason = models.CharField(max_length=255, blank=True)
    void_movement = models.OneToOneField(
        POSCashMovement, null=True, blank=True,
        on_delete=models.PROTECT, related_name="voided_expense",
    )

    class Meta:
        verbose_name = _("POS expense")
        verbose_name_plural = _("POS expenses")
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(check=models.Q(amount__gt=0), name="pos_expense_amount_positive"),
        ]

    def __str__(self):
        return f"{self.get_payment_mode_display()} ₹{self.amount} — {self.remarks[:40]}"

    @property
    def is_voided(self) -> bool:
        return self.voided_at is not None
