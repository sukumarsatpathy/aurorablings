"""
inventory.models
~~~~~~~~~~~~~~~~

Architecture: Ledger + Cache hybrid
────────────────────────────────────
  StockLedger    – immutable append-only log of every stock change
  WarehouseStock – cached summary per (variant, warehouse)
                   holds: on_hand, reserved, available
                   recomputable from ledger at any time

Key invariant:
    available = on_hand - reserved   (always)

Every mutation goes through a service that:
  1. select_for_update() on WarehouseStock — prevents concurrent over-sell
  2. validates the operation
  3. writes an immutable StockLedger row
  4. updates the WarehouseStock cache

Models in this file:
  Warehouse
  WarehouseStock
  StockLedger
  StockReservation
"""

import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator


# ─────────────────────────────────────────────────────────────
#  Warehouse / Location
# ─────────────────────────────────────────────────────────────

class WarehouseType(models.TextChoices):
    WAREHOUSE = "warehouse", _("Warehouse")
    STORE     = "store",     _("Retail Store")
    VIRTUAL   = "virtual",   _("Virtual / Dropship")


class Warehouse(models.Model):
    """
    A physical or virtual stock location.
    Products can have stock at multiple locations.
    """

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name        = models.CharField(max_length=200, unique=True)
    code        = models.SlugField(max_length=50,  unique=True, db_index=True)
    type        = models.CharField(max_length=20, choices=WarehouseType.choices, default=WarehouseType.WAREHOUSE)
    address     = models.TextField(blank=True)
    is_active   = models.BooleanField(default=True)
    is_default  = models.BooleanField(default=False)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = _("warehouse")
        verbose_name_plural = _("warehouses")
        ordering            = ["-is_default", "name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


# ─────────────────────────────────────────────────────────────
#  Warehouse Stock  (cached summary — source of truth for locks)
# ─────────────────────────────────────────────────────────────

class WarehouseStock(models.Model):
    """
    Cached stock position for one (variant, warehouse) pair.

    Fields:
        on_hand   – physically present units
        reserved  – held for pending orders (not yet shipped)
        available – on_hand - reserved  (auto-maintained)

    ⚠ NEVER update these fields directly.
    Always go through inventory.services which:
      1. acquires a SELECT FOR UPDATE lock on this row
      2. validates the change
      3. writes a StockLedger entry
      4. updates on_hand / reserved / available atomically
    """

    id        = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    variant   = models.ForeignKey(
        "catalog.ProductVariant",
        on_delete=models.CASCADE,
        related_name="stock_records",
    )
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        related_name="stock_records",
    )

    on_hand   = models.IntegerField(default=0)
    reserved  = models.IntegerField(default=0)
    available = models.IntegerField(default=0)   # denormalised: on_hand - reserved

    low_stock_threshold = models.PositiveSmallIntegerField(default=5)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together     = [("variant", "warehouse")]
        verbose_name        = _("warehouse stock")
        verbose_name_plural = _("warehouse stocks")
        indexes             = [
            models.Index(fields=["variant", "warehouse"]),
            models.Index(fields=["available"]),
        ]

    @property
    def is_in_stock(self) -> bool:
        return self.available > 0

    @property
    def is_low_stock(self) -> bool:
        return self.is_in_stock and self.available <= self.low_stock_threshold

    def __str__(self):
        return f"{self.variant.sku} @ {self.warehouse.code}: on_hand={self.on_hand} reserved={self.reserved}"


# ─────────────────────────────────────────────────────────────
#  Movement Types
# ─────────────────────────────────────────────────────────────

class MovementType(models.TextChoices):
    # ── Stock in ──────────────────────────────────────────────
    PURCHASE         = "purchase",         _("Purchase / Receipt")
    RETURN           = "return",           _("Customer Return")
    EXCHANGE_IN      = "exchange_in",      _("Exchange — Incoming")
    ADJUSTMENT_IN    = "adjustment_in",    _("Manual Adjustment In")
    TRANSFER_IN      = "transfer_in",      _("Transfer In")

    # ── Stock out ─────────────────────────────────────────────
    SALE             = "sale",             _("Sale")
    EXCHANGE_OUT     = "exchange_out",     _("Exchange — Outgoing")
    ADJUSTMENT_OUT   = "adjustment_out",   _("Manual Adjustment Out")
    DAMAGE           = "damage",           _("Damaged / Shrinkage")
    TRANSFER_OUT     = "transfer_out",     _("Transfer Out")

    # ── Reservation lifecycle ─────────────────────────────────
    RESERVATION      = "reservation",      _("Reservation")
    RESERVATION_RELEASE = "reservation_release", _("Reservation Release")
    RESERVATION_COMMIT  = "reservation_commit",  _("Reservation Commit → Sale")

# Movements that increase on_hand
INBOUND_MOVEMENTS = {
    MovementType.PURCHASE,
    MovementType.RETURN,
    MovementType.EXCHANGE_IN,
    MovementType.ADJUSTMENT_IN,
    MovementType.TRANSFER_IN,
}

# Movements that decrease on_hand
OUTBOUND_MOVEMENTS = {
    MovementType.SALE,
    MovementType.EXCHANGE_OUT,
    MovementType.ADJUSTMENT_OUT,
    MovementType.DAMAGE,
    MovementType.TRANSFER_OUT,
    MovementType.RESERVATION_COMMIT,
}


# ─────────────────────────────────────────────────────────────
#  Reference Types (what triggered this movement)
# ─────────────────────────────────────────────────────────────

class ReferenceType(models.TextChoices):
    ORDER    = "order",    _("Order")
    RETURN   = "return",   _("Return")
    EXCHANGE = "exchange", _("Exchange")
    TRANSFER = "transfer", _("Transfer")
    MANUAL   = "manual",   _("Manual")
    SYSTEM   = "system",   _("System")


# ─────────────────────────────────────────────────────────────
#  Stock Ledger  (append-only, never mutated)
# ─────────────────────────────────────────────────────────────

class StockLedger(models.Model):
    """
    Immutable audit trail of every stock movement.

    Design rules:
      - Rows are NEVER updated or deleted.
      - quantity is SIGNED:  positive = stock in, negative = stock out.
      - The current on_hand can always be recomputed:
            SUM(quantity) WHERE type NOT IN (RESERVATION, RESERVATION_RELEASE)
    """

    id            = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    stock_record  = models.ForeignKey(
        WarehouseStock,
        on_delete=models.PROTECT,
        related_name="ledger_entries",
    )
    movement_type    = models.CharField(max_length=30, choices=MovementType.choices, db_index=True)
    reference_type   = models.CharField(max_length=20, choices=ReferenceType.choices, db_index=True)
    reference_id     = models.CharField(max_length=100, blank=True, db_index=True,
                                        help_text="Order ID, Return ID, etc.")

    # Signed quantity: +N = stock arrives, -N = stock leaves
    quantity         = models.IntegerField(
        help_text="Positive = stock in. Negative = stock out.",
    )

    # Snapshot of totals AFTER this entry (for debugging / audit)
    on_hand_after    = models.IntegerField()
    reserved_after   = models.IntegerField()
    available_after  = models.IntegerField()

    notes      = models.TextField(blank=True)
    created_by = models.ForeignKey(
        "accounts.User",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="stock_movements",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name        = _("stock ledger entry")
        verbose_name_plural = _("stock ledger entries")
        ordering            = ["-created_at"]
        indexes             = [
            models.Index(fields=["stock_record", "movement_type"]),
            models.Index(fields=["reference_type", "reference_id"]),
        ]

    def __str__(self):
        sign = "+" if self.quantity >= 0 else ""
        return (
            f"{self.movement_type} {sign}{self.quantity} "
            f"→ {self.stock_record.variant.sku} "
            f"@ {self.stock_record.warehouse.code}"
        )


# ─────────────────────────────────────────────────────────────
#  Stock Reservation
# ─────────────────────────────────────────────────────────────

class ReservationStatus(models.TextChoices):
    ACTIVE    = "active",    _("Active")
    COMMITTED = "committed", _("Committed")   # order fulfilled, stock deducted
    RELEASED  = "released",  _("Released")    # order cancelled, stock freed


class StockReservation(models.Model):
    """
    Tracks quantity reserved for a specific order / reference.

    Lifecycle:
      ACTIVE     – stock is held, not yet deducted from on_hand
      COMMITTED  – order shipped; reserved qty converted to a SALE ledger entry
      RELEASED   – order cancelled; reserved qty freed

    A reservation is linked to a (stock_record, reference_id) pair.
    Only one ACTIVE reservation per (stock_record, reference_id) is allowed.
    """

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    stock_record = models.ForeignKey(
        WarehouseStock,
        on_delete=models.PROTECT,
        related_name="reservations",
    )
    reference_type = models.CharField(max_length=20, choices=ReferenceType.choices)
    reference_id   = models.CharField(max_length=100, db_index=True)

    quantity       = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    status         = models.CharField(
        max_length=15,
        choices=ReservationStatus.choices,
        default=ReservationStatus.ACTIVE,
        db_index=True,
    )
    expires_at   = models.DateTimeField(
        null=True, blank=True,
        help_text="Auto-release after this time if still ACTIVE.",
    )
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = _("stock reservation")
        verbose_name_plural = _("stock reservations")
        ordering            = ["-created_at"]
        indexes             = [
            models.Index(fields=["reference_type", "reference_id", "status"]),
            models.Index(fields=["stock_record", "status"]),
        ]
        constraints         = [
            models.UniqueConstraint(
                fields=["stock_record", "reference_id"],
                condition=models.Q(status="active"),
                name="unique_active_reservation_per_reference",
            )
        ]

    def __str__(self):
        return (
            f"[{self.status}] {self.quantity}u reserved for "
            f"{self.reference_type}#{self.reference_id} "
            f"— {self.stock_record.variant.sku}"
        )
