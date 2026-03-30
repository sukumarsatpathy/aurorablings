"""
inventory.services
~~~~~~~~~~~~~~~~~~
All stock mutation logic.

Concurrency safety model:
──────────────────────────
Every public function that modifies stock must:

  1.  Be wrapped in @transaction.atomic
  2.  Call _get_stock_record_for_update() which issues
      SELECT ... FOR UPDATE on WarehouseStock — this serialises
      concurrent requests for the same (variant, warehouse) pair
      at the database level.
  3.  Validate available quantity AFTER acquiring the lock.
  4.  Write an immutable StockLedger row.
  5.  Update WarehouseStock counters atomically within the same tx.

This pattern prevents double-spending under load without application-
level locking or external queues.

Public API:
    receive_stock()           – purchase / goods-in
    reserve_stock()           – hold stock for an order
    release_reservation()     – cancel → free stock
    commit_reservation()      – ship → deduct from on_hand
    process_return()          – customer return → stock back in
    process_exchange()        – swap one variant for another
    adjust_stock()            – manual correction
    transfer_stock()          – move stock between warehouses
    recompute_stock()         – rebuild WarehouseStock from ledger (admin tool)
"""

from __future__ import annotations

from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from core.logging import get_logger
from audit.models import ActorType, AuditAction
from audit.services.activity_logger import log_activity
from .models import (
    Warehouse, WarehouseStock, StockLedger, StockReservation,
    MovementType, ReferenceType, ReservationStatus,
    INBOUND_MOVEMENTS, OUTBOUND_MOVEMENTS,
)
from .exceptions import (
    InsufficientStockError,
    StockReservationError,
    InvalidMovementError,
    WarehouseNotFoundError,
)

logger = get_logger(__name__)


def _actor_for_user(user) -> str:
    if not user or not getattr(user, "is_authenticated", False):
        return ActorType.SYSTEM
    if getattr(user, "role", "") == "admin":
        return ActorType.ADMIN
    if getattr(user, "role", "") == "staff":
        return ActorType.STAFF
    return ActorType.CUSTOMER


def _log_inventory_activity(*, created_by, action: str, entity_id: str, description: str, metadata: dict) -> None:
    log_activity(
        user=created_by if created_by and getattr(created_by, "is_authenticated", False) else None,
        actor_type=_actor_for_user(created_by),
        action=action,
        entity_type="inventory",
        entity_id=entity_id,
        description=description,
        metadata=metadata,
    )


# ─────────────────────────────────────────────────────────────
#  1. Receive Stock  (purchase / goods-in)
# ─────────────────────────────────────────────────────────────

@transaction.atomic
def receive_stock(
    *,
    variant_id,
    warehouse_id,
    quantity: int,
    reference_id: str = "",
    notes: str = "",
    created_by=None,
) -> StockLedger:
    """
    Record inbound stock from a purchase order or manual receipt.

    quantity must be positive.
    Creates / initialises a WarehouseStock record if none exists.
    """
    _validate_positive(quantity, "quantity")

    stock = _get_or_create_stock_record(variant_id, warehouse_id)
    stock = _lock(stock)

    stock.on_hand   += quantity
    stock.available  = stock.on_hand - stock.reserved
    stock.save(update_fields=["on_hand", "available", "updated_at"])

    entry = _write_ledger(
        stock=stock,
        movement_type=MovementType.PURCHASE,
        reference_type=ReferenceType.MANUAL,
        reference_id=reference_id,
        quantity=+quantity,
        notes=notes,
        created_by=created_by,
    )
    logger.info(
        "stock_received",
        sku=stock.variant.sku,
        warehouse=stock.warehouse.code,
        quantity=quantity,
        on_hand=stock.on_hand,
    )
    _log_inventory_activity(
        created_by=created_by,
        action=AuditAction.UPDATE,
        entity_id=str(stock.id),
        description=f"Received {quantity} units for SKU {stock.variant.sku}",
        metadata={
            "movement_type": MovementType.PURCHASE,
            "sku": stock.variant.sku,
            "warehouse": stock.warehouse.code,
            "quantity": quantity,
            "on_hand_after": stock.on_hand,
            "available_after": stock.available,
            "reference_id": reference_id,
        },
    )
    return entry


# ─────────────────────────────────────────────────────────────
#  2. Reserve Stock  (hold for pending order)
# ─────────────────────────────────────────────────────────────

@transaction.atomic
def reserve_stock(
    *,
    variant_id,
    warehouse_id,
    quantity: int,
    order_id: str,
    reference_type: str = ReferenceType.ORDER,
    expires_at=None,
    created_by=None,
) -> StockReservation:
    """
    Reserve `quantity` units for an order.

    Raises InsufficientStockError if available < quantity.
    Raises StockReservationError if a reservation for this order already exists.
    """
    _validate_positive(quantity, "quantity")

    stock = _get_or_create_stock_record(variant_id, warehouse_id)
    stock = _lock(stock)

    # Guard: duplicate reservation?
    if StockReservation.objects.filter(
        stock_record=stock, reference_id=order_id, status=ReservationStatus.ACTIVE
    ).exists():
        raise StockReservationError(
            f"An active reservation already exists for order '{order_id}'."
        )

    # Guard: enough stock?
    if stock.available < quantity:
        raise InsufficientStockError(
            sku=stock.variant.sku,
            requested=quantity,
            available=stock.available,
            warehouse=stock.warehouse.code,
        )

    stock.reserved  += quantity
    stock.available  = stock.on_hand - stock.reserved
    stock.save(update_fields=["reserved", "available", "updated_at"])

    reservation = StockReservation.objects.create(
        stock_record=stock,
        reference_type=reference_type,
        reference_id=order_id,
        quantity=quantity,
        status=ReservationStatus.ACTIVE,
        expires_at=expires_at,
    )

    _write_ledger(
        stock=stock,
        movement_type=MovementType.RESERVATION,
        reference_type=reference_type,
        reference_id=order_id,
        quantity=-quantity,          # signed: reduces available, not on_hand
        notes=f"Reserved for {reference_type} #{order_id}",
        created_by=created_by,
    )
    logger.info(
        "stock_reserved",
        sku=stock.variant.sku,
        warehouse=stock.warehouse.code,
        quantity=quantity,
        order_id=order_id,
        available_after=stock.available,
    )
    _log_inventory_activity(
        created_by=created_by,
        action=AuditAction.STATUS_CHANGE,
        entity_id=str(reservation.id),
        description=f"Reserved {quantity} units for order {order_id}",
        metadata={
            "movement_type": MovementType.RESERVATION,
            "sku": stock.variant.sku,
            "warehouse": stock.warehouse.code,
            "quantity": quantity,
            "order_id": order_id,
            "reserved_after": stock.reserved,
            "available_after": stock.available,
        },
    )
    return reservation


# ─────────────────────────────────────────────────────────────
#  3. Release Reservation  (order cancelled)
# ─────────────────────────────────────────────────────────────

@transaction.atomic
def release_reservation(
    *,
    order_id: str,
    variant_id=None,
    warehouse_id=None,
    notes: str = "Order cancelled",
    created_by=None,
) -> list[StockReservation]:
    """
    Release ALL active reservations for an order.
    Returns the list of reservations that were released.

    Optionally scope to a specific variant/warehouse for partial releases.
    """
    qs = StockReservation.objects.filter(
        reference_id=order_id,
        status=ReservationStatus.ACTIVE,
    ).select_related("stock_record__variant", "stock_record__warehouse")

    if variant_id:
        qs = qs.filter(stock_record__variant_id=variant_id)
    if warehouse_id:
        qs = qs.filter(stock_record__warehouse_id=warehouse_id)

    released = []
    for reservation in qs:
        stock = _lock(reservation.stock_record)

        stock.reserved  = max(0, stock.reserved - reservation.quantity)
        stock.available = stock.on_hand - stock.reserved
        stock.save(update_fields=["reserved", "available", "updated_at"])

        reservation.status = ReservationStatus.RELEASED
        reservation.save(update_fields=["status", "updated_at"])

        _write_ledger(
            stock=stock,
            movement_type=MovementType.RESERVATION_RELEASE,
            reference_type=reservation.reference_type,
            reference_id=order_id,
            quantity=+reservation.quantity,     # restores available
            notes=notes,
            created_by=created_by,
        )
        released.append(reservation)
        logger.info(
            "reservation_released",
            sku=stock.variant.sku,
            warehouse=stock.warehouse.code,
            quantity=reservation.quantity,
            order_id=order_id,
        )
        _log_inventory_activity(
            created_by=created_by,
            action=AuditAction.STATUS_CHANGE,
            entity_id=str(reservation.id),
            description=f"Released reservation for order {order_id}",
            metadata={
                "movement_type": MovementType.RESERVATION_RELEASE,
                "sku": stock.variant.sku,
                "warehouse": stock.warehouse.code,
                "quantity": reservation.quantity,
                "order_id": order_id,
                "reserved_after": stock.reserved,
                "available_after": stock.available,
            },
        )
    return released


# ─────────────────────────────────────────────────────────────
#  4. Commit Reservation  (order fulfilled / shipped)
# ─────────────────────────────────────────────────────────────

@transaction.atomic
def commit_reservation(
    *,
    order_id: str,
    variant_id=None,
    notes: str = "Order fulfilled",
    created_by=None,
) -> list[StockReservation]:
    """
    Commit ALL active reservations for an order:
      - Decrements on_hand (physical deduction)
      - Decrements reserved (clears the hold)
      - available remains the same (was already excluded from available)
      - Marks reservations as COMMITTED
      - Writes RESERVATION_COMMIT ledger entry
    """
    qs = StockReservation.objects.filter(
        reference_id=order_id,
        status=ReservationStatus.ACTIVE,
    ).select_related("stock_record__variant", "stock_record__warehouse")

    if variant_id:
        qs = qs.filter(stock_record__variant_id=variant_id)

    if not qs.exists():
        raise StockReservationError(
            f"No active reservations found for order '{order_id}'."
        )

    committed = []
    for reservation in qs:
        stock = _lock(reservation.stock_record)

        if stock.on_hand < reservation.quantity:
            raise InsufficientStockError(
                sku=stock.variant.sku,
                requested=reservation.quantity,
                available=stock.on_hand,
                warehouse=stock.warehouse.code,
            )

        stock.on_hand  -= reservation.quantity
        stock.reserved  = max(0, stock.reserved - reservation.quantity)
        stock.available = stock.on_hand - stock.reserved
        stock.save(update_fields=["on_hand", "reserved", "available", "updated_at"])

        reservation.status = ReservationStatus.COMMITTED
        reservation.save(update_fields=["status", "updated_at"])

        _write_ledger(
            stock=stock,
            movement_type=MovementType.RESERVATION_COMMIT,
            reference_type=ReferenceType.ORDER,
            reference_id=order_id,
            quantity=-reservation.quantity,
            notes=notes,
            created_by=created_by,
        )
        committed.append(reservation)
        logger.info(
            "reservation_committed",
            sku=stock.variant.sku,
            warehouse=stock.warehouse.code,
            quantity=reservation.quantity,
            order_id=order_id,
            on_hand_after=stock.on_hand,
        )
        _log_inventory_activity(
            created_by=created_by,
            action=AuditAction.STATUS_CHANGE,
            entity_id=str(reservation.id),
            description=f"Committed reservation for order {order_id}",
            metadata={
                "movement_type": MovementType.RESERVATION_COMMIT,
                "sku": stock.variant.sku,
                "warehouse": stock.warehouse.code,
                "quantity": reservation.quantity,
                "order_id": order_id,
                "on_hand_after": stock.on_hand,
                "reserved_after": stock.reserved,
            },
        )
    return committed


# ─────────────────────────────────────────────────────────────
#  5. Process Return  (customer returns items)
# ─────────────────────────────────────────────────────────────

@transaction.atomic
def process_return(
    *,
    variant_id,
    warehouse_id,
    quantity: int,
    return_id: str,
    return_to_stock: bool = True,
    notes: str = "",
    created_by=None,
) -> StockLedger | None:
    """
    Handle a customer return.

    return_to_stock=True  → items go back to available inventory
    return_to_stock=False → items are damaged/quarantined (no stock change,
                            just a DAMAGE ledger entry for audit)
    """
    _validate_positive(quantity, "quantity")

    if not return_to_stock:
        stock = _get_or_create_stock_record(variant_id, warehouse_id)
        stock = _lock(stock)
        entry = _write_ledger(
            stock=stock,
            movement_type=MovementType.DAMAGE,
            reference_type=ReferenceType.RETURN,
            reference_id=return_id,
            quantity=0,     # no physical change — quarantine log only
            notes=notes or "Return quarantined — not restocked.",
            created_by=created_by,
        )
        logger.info("return_quarantined", return_id=return_id, quantity=quantity)
        _log_inventory_activity(
            created_by=created_by,
            action=AuditAction.UPDATE,
            entity_id=str(stock.id),
            description=f"Processed return {return_id} without restocking",
            metadata={
                "movement_type": MovementType.DAMAGE,
                "return_id": return_id,
                "quantity": quantity,
                "sku": stock.variant.sku,
                "warehouse": stock.warehouse.code,
            },
        )
        return entry

    stock = _get_or_create_stock_record(variant_id, warehouse_id)
    stock = _lock(stock)

    stock.on_hand   += quantity
    stock.available  = stock.on_hand - stock.reserved
    stock.save(update_fields=["on_hand", "available", "updated_at"])

    entry = _write_ledger(
        stock=stock,
        movement_type=MovementType.RETURN,
        reference_type=ReferenceType.RETURN,
        reference_id=return_id,
        quantity=+quantity,
        notes=notes or f"Customer return #{return_id}",
        created_by=created_by,
    )
    logger.info(
        "return_processed",
        sku=stock.variant.sku,
        warehouse=stock.warehouse.code,
        quantity=quantity,
        return_id=return_id,
        on_hand_after=stock.on_hand,
    )
    _log_inventory_activity(
        created_by=created_by,
        action=AuditAction.UPDATE,
        entity_id=str(stock.id),
        description=f"Restocked return {return_id}",
        metadata={
            "movement_type": MovementType.RETURN,
            "return_id": return_id,
            "quantity": quantity,
            "sku": stock.variant.sku,
            "warehouse": stock.warehouse.code,
            "on_hand_after": stock.on_hand,
            "available_after": stock.available,
        },
    )
    return entry


# ─────────────────────────────────────────────────────────────
#  6. Process Exchange
# ─────────────────────────────────────────────────────────────

@transaction.atomic
def process_exchange(
    *,
    exchange_id: str,
    warehouse_id,
    outgoing_variant_id,
    outgoing_quantity: int,
    incoming_variant_id,
    incoming_quantity: int,
    notes: str = "",
    created_by=None,
) -> dict:
    """
    Process an exchange: customer sends back `incoming_variant` and
    receives `outgoing_variant`.

    Steps:
      1. Deduct outgoing_variant from stock (EXCHANGE_OUT)
      2. Add  incoming_variant to stock  (EXCHANGE_IN)

    Raises InsufficientStockError if outgoing stock is unavailable.

    Returns {"out": StockLedger, "in": StockLedger}
    """
    _validate_positive(outgoing_quantity, "outgoing_quantity")
    _validate_positive(incoming_quantity, "incoming_quantity")

    # ── Outgoing stock (what we send to customer) ─────────────
    out_stock = _get_or_create_stock_record(outgoing_variant_id, warehouse_id)
    out_stock = _lock(out_stock)

    if out_stock.available < outgoing_quantity:
        raise InsufficientStockError(
            sku=out_stock.variant.sku,
            requested=outgoing_quantity,
            available=out_stock.available,
            warehouse=out_stock.warehouse.code,
        )

    out_stock.on_hand   -= outgoing_quantity
    out_stock.available  = out_stock.on_hand - out_stock.reserved
    out_stock.save(update_fields=["on_hand", "available", "updated_at"])

    out_entry = _write_ledger(
        stock=out_stock,
        movement_type=MovementType.EXCHANGE_OUT,
        reference_type=ReferenceType.EXCHANGE,
        reference_id=exchange_id,
        quantity=-outgoing_quantity,
        notes=notes,
        created_by=created_by,
    )

    # ── Incoming stock (what customer returns) ─────────────────
    in_stock = _get_or_create_stock_record(incoming_variant_id, warehouse_id)
    in_stock = _lock(in_stock)

    in_stock.on_hand   += incoming_quantity
    in_stock.available  = in_stock.on_hand - in_stock.reserved
    in_stock.save(update_fields=["on_hand", "available", "updated_at"])

    in_entry = _write_ledger(
        stock=in_stock,
        movement_type=MovementType.EXCHANGE_IN,
        reference_type=ReferenceType.EXCHANGE,
        reference_id=exchange_id,
        quantity=+incoming_quantity,
        notes=notes,
        created_by=created_by,
    )
    logger.info(
        "exchange_processed",
        exchange_id=exchange_id,
        out_sku=out_stock.variant.sku,
        out_qty=outgoing_quantity,
        in_sku=in_stock.variant.sku,
        in_qty=incoming_quantity,
    )
    _log_inventory_activity(
        created_by=created_by,
        action=AuditAction.UPDATE,
        entity_id=str(out_stock.id),
        description=f"Processed exchange {exchange_id}",
        metadata={
            "exchange_id": exchange_id,
            "outgoing_sku": out_stock.variant.sku,
            "outgoing_qty": outgoing_quantity,
            "incoming_sku": in_stock.variant.sku,
            "incoming_qty": incoming_quantity,
            "warehouse": out_stock.warehouse.code,
        },
    )
    return {"out": out_entry, "in": in_entry}


# ─────────────────────────────────────────────────────────────
#  7. Manual Adjustment
# ─────────────────────────────────────────────────────────────

@transaction.atomic
def adjust_stock(
    *,
    variant_id,
    warehouse_id,
    quantity_delta: int,
    reason: str,
    created_by=None,
) -> StockLedger:
    """
    Apply a signed quantity delta to on_hand for correction purposes.

    quantity_delta > 0 → add stock (ADJUSTMENT_IN)
    quantity_delta < 0 → remove stock (ADJUSTMENT_OUT)

    Raises InvalidMovementError if the adjustment would make on_hand negative.
    """
    if quantity_delta == 0:
        raise InvalidMovementError("Adjustment quantity cannot be zero.")

    stock = _get_or_create_stock_record(variant_id, warehouse_id)
    stock = _lock(stock)

    new_on_hand = stock.on_hand + quantity_delta
    if new_on_hand < 0:
        raise InvalidMovementError(
            f"Adjustment of {quantity_delta} would make on_hand negative "
            f"(current: {stock.on_hand}). Use DAMAGE movement type for write-offs."
        )

    movement = MovementType.ADJUSTMENT_IN if quantity_delta > 0 else MovementType.ADJUSTMENT_OUT
    stock.on_hand   = new_on_hand
    stock.available = stock.on_hand - stock.reserved
    stock.save(update_fields=["on_hand", "available", "updated_at"])

    entry = _write_ledger(
        stock=stock,
        movement_type=movement,
        reference_type=ReferenceType.MANUAL,
        reference_id="",
        quantity=quantity_delta,
        notes=reason,
        created_by=created_by,
    )
    logger.info(
        "stock_adjusted",
        sku=stock.variant.sku,
        warehouse=stock.warehouse.code,
        delta=quantity_delta,
        on_hand_after=stock.on_hand,
        reason=reason,
    )
    _log_inventory_activity(
        created_by=created_by,
        action=AuditAction.UPDATE,
        entity_id=str(stock.id),
        description=f"Adjusted stock for SKU {stock.variant.sku}",
        metadata={
            "movement_type": movement,
            "sku": stock.variant.sku,
            "warehouse": stock.warehouse.code,
            "quantity_delta": quantity_delta,
            "on_hand_after": stock.on_hand,
            "available_after": stock.available,
            "reason": reason,
        },
    )
    return entry


# ─────────────────────────────────────────────────────────────
#  8. Transfer Between Warehouses
# ─────────────────────────────────────────────────────────────

@transaction.atomic
def transfer_stock(
    *,
    variant_id,
    from_warehouse_id,
    to_warehouse_id,
    quantity: int,
    transfer_id: str = "",
    notes: str = "",
    created_by=None,
) -> dict:
    """
    Move stock from one warehouse to another atomically.
    Returns {"out": StockLedger, "in": StockLedger}
    """
    _validate_positive(quantity, "quantity")

    if str(from_warehouse_id) == str(to_warehouse_id):
        raise InvalidMovementError("Source and destination warehouse cannot be the same.")

    from_stock = _get_or_create_stock_record(variant_id, from_warehouse_id)
    from_stock = _lock(from_stock)

    if from_stock.available < quantity:
        raise InsufficientStockError(
            sku=from_stock.variant.sku,
            requested=quantity,
            available=from_stock.available,
            warehouse=from_stock.warehouse.code,
        )

    from_stock.on_hand   -= quantity
    from_stock.available  = from_stock.on_hand - from_stock.reserved
    from_stock.save(update_fields=["on_hand", "available", "updated_at"])

    out_entry = _write_ledger(
        stock=from_stock,
        movement_type=MovementType.TRANSFER_OUT,
        reference_type=ReferenceType.TRANSFER,
        reference_id=transfer_id,
        quantity=-quantity,
        notes=notes,
        created_by=created_by,
    )

    to_stock = _get_or_create_stock_record(variant_id, to_warehouse_id)
    to_stock = _lock(to_stock)

    to_stock.on_hand   += quantity
    to_stock.available  = to_stock.on_hand - to_stock.reserved
    to_stock.save(update_fields=["on_hand", "available", "updated_at"])

    in_entry = _write_ledger(
        stock=to_stock,
        movement_type=MovementType.TRANSFER_IN,
        reference_type=ReferenceType.TRANSFER,
        reference_id=transfer_id,
        quantity=+quantity,
        notes=notes,
        created_by=created_by,
    )
    logger.info(
        "stock_transferred",
        sku=from_stock.variant.sku,
        from_warehouse=from_stock.warehouse.code,
        to_warehouse=to_stock.warehouse.code,
        quantity=quantity,
    )
    _log_inventory_activity(
        created_by=created_by,
        action=AuditAction.UPDATE,
        entity_id=transfer_id or f"{from_stock.id}:{to_stock.id}",
        description=f"Transferred {quantity} units of SKU {from_stock.variant.sku}",
        metadata={
            "movement_type": "transfer",
            "sku": from_stock.variant.sku,
            "quantity": quantity,
            "from_warehouse": from_stock.warehouse.code,
            "to_warehouse": to_stock.warehouse.code,
            "from_on_hand_after": from_stock.on_hand,
            "to_on_hand_after": to_stock.on_hand,
            "transfer_id": transfer_id,
        },
    )
    return {"out": out_entry, "in": in_entry}


# ─────────────────────────────────────────────────────────────
#  9. Recompute from Ledger  (admin / repair tool)
# ─────────────────────────────────────────────────────────────

@transaction.atomic
def recompute_stock(*, stock_record: WarehouseStock) -> WarehouseStock:
    """
    Rebuild WarehouseStock counters from the ledger.
    Use when the cached values become suspect.

    on_hand  = SUM of all ledger quantities (excluding reservation-only entries)
    reserved = SUM of active StockReservation quantities
    available = on_hand - reserved
    """
    from django.db.models import Sum

    physical_types = list(INBOUND_MOVEMENTS | OUTBOUND_MOVEMENTS)
    on_hand = (
        StockLedger.objects
        .filter(stock_record=stock_record, movement_type__in=physical_types)
        .aggregate(total=Sum("quantity"))["total"] or 0
    )
    reserved = (
        StockReservation.objects
        .filter(stock_record=stock_record, status=ReservationStatus.ACTIVE)
        .aggregate(total=Sum("quantity"))["total"] or 0
    )

    stock_record = _lock(stock_record)
    stock_record.on_hand   = max(0, on_hand)
    stock_record.reserved  = max(0, reserved)
    stock_record.available = max(0, stock_record.on_hand - stock_record.reserved)
    stock_record.save(update_fields=["on_hand", "reserved", "available", "updated_at"])

    logger.info(
        "stock_recomputed",
        stock_record_id=str(stock_record.id),
        on_hand=stock_record.on_hand,
        reserved=stock_record.reserved,
        available=stock_record.available,
    )
    return stock_record


# ─────────────────────────────────────────────────────────────
#  Warehouse management helpers
# ─────────────────────────────────────────────────────────────

def create_warehouse(*, name: str, code: str, type: str = "warehouse", **kwargs) -> Warehouse:
    from core.exceptions import ConflictError
    if Warehouse.objects.filter(code=code).exists():
        raise ConflictError(f"Warehouse code '{code}' already in use.")
    return Warehouse.objects.create(name=name, code=code, type=type, **kwargs)


# ─────────────────────────────────────────────────────────────
#  Private helpers
# ─────────────────────────────────────────────────────────────

def _lock(stock: WarehouseStock) -> WarehouseStock:
    """
    Re-fetch and lock the WarehouseStock row with SELECT FOR UPDATE.
    Must be called inside an @transaction.atomic block.
    """
    return WarehouseStock.objects.select_for_update().get(pk=stock.pk)


def _get_or_create_stock_record(variant_id, warehouse_id) -> WarehouseStock:
    """
    Return (or create) the WarehouseStock row for a (variant, warehouse) pair.
    WARNING: do not lock here — call _lock() afterward inside the tx.
    """
    stock, _ = WarehouseStock.objects.get_or_create(
        variant_id=variant_id,
        warehouse_id=warehouse_id,
        defaults={"on_hand": 0, "reserved": 0, "available": 0},
    )
    return stock


def _write_ledger(
    *,
    stock: WarehouseStock,
    movement_type: str,
    reference_type: str,
    reference_id: str,
    quantity: int,
    notes: str = "",
    created_by=None,
) -> StockLedger:
    return StockLedger.objects.create(
        stock_record=stock,
        movement_type=movement_type,
        reference_type=reference_type,
        reference_id=reference_id,
        quantity=quantity,
        on_hand_after=stock.on_hand,
        reserved_after=stock.reserved,
        available_after=stock.available,
        notes=notes,
        created_by=created_by,
    )


def _validate_positive(value: int, field: str) -> None:
    if not isinstance(value, int) or value <= 0:
        raise InvalidMovementError(f"'{field}' must be a positive integer, got {value!r}.")
