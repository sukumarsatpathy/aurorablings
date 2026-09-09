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
