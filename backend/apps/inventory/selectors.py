"""
inventory.selectors
~~~~~~~~~~~~~~~~~~~
Read-only query helpers for the inventory system.
All functions are safe to cache (no side effects).
"""

from __future__ import annotations

from django.db.models import QuerySet, Sum, Q
from apps.catalog.models import ProductVariant
from .models import Warehouse, WarehouseStock, StockLedger, StockReservation, ReservationStatus


# ─────────────────────────────────────────────────────────────
#  Warehouse
# ─────────────────────────────────────────────────────────────

def get_default_warehouse() -> Warehouse | None:
    return Warehouse.objects.filter(is_default=True, is_active=True).first()


def get_warehouse_by_id(warehouse_id) -> Warehouse | None:
    try:
        return Warehouse.objects.get(id=warehouse_id)
    except Warehouse.DoesNotExist:
        return None


def get_warehouse_by_code(code: str) -> Warehouse | None:
    try:
        return Warehouse.objects.get(code=code)
    except Warehouse.DoesNotExist:
        return None


def get_all_warehouses(*, active_only: bool = True) -> QuerySet:
    qs = Warehouse.objects.all()
    if active_only:
        qs = qs.filter(is_active=True)
    return qs.order_by("-is_default", "name")


# ─────────────────────────────────────────────────────────────
#  Stock Levels
# ─────────────────────────────────────────────────────────────

def get_stock_for_variant(variant_id, warehouse_id=None) -> WarehouseStock | None:
    """
    Return a single stock record.
    If no warehouse given, uses the default warehouse.
    """
    if warehouse_id is None:
        wh = get_default_warehouse()
        if not wh:
            return None
        warehouse_id = wh.id
    try:
        return (
            WarehouseStock.objects
            .select_related("variant", "warehouse")
            .get(variant_id=variant_id, warehouse_id=warehouse_id)
        )
    except WarehouseStock.DoesNotExist:
        return None


def get_stock_across_warehouses(variant_id) -> QuerySet:
    """All stock records for a variant, across all locations."""
    return (
        WarehouseStock.objects
        .filter(variant_id=variant_id)
        .select_related("variant__product", "warehouse")
        .order_by("-warehouse__is_default", "warehouse__name")
    )


def get_stock_record_by_id(stock_record_id) -> WarehouseStock | None:
    try:
        return (
            WarehouseStock.objects
            .select_related("variant__product", "warehouse")
            .get(id=stock_record_id)
        )
    except WarehouseStock.DoesNotExist:
        return None


def get_all_stock_records(
    *,
    search: str | None = None,
    warehouse_id=None,
    status: str | None = None,
) -> QuerySet:
    qs = WarehouseStock.objects.select_related("variant__product", "warehouse")

    if search:
        qs = qs.filter(
            Q(variant__sku__icontains=search) |
            Q(variant__name__icontains=search) |
            Q(variant__product__name__icontains=search)
        )

    if warehouse_id:
        qs = qs.filter(warehouse_id=warehouse_id)

    if status == "low":
        from django.db.models import F
        qs = qs.filter(available__gt=0, available__lte=F("low_stock_threshold"))
    elif status == "out":
        qs = qs.filter(available__lte=0)
    elif status == "in":
        qs = qs.filter(available__gt=0)

    return qs.order_by("variant__product__name", "variant__sku", "warehouse__name")


def get_variant_options(*, search: str | None = None, active_only: bool = True) -> QuerySet:
    qs = ProductVariant.objects.select_related("product", "product__category").prefetch_related("product__media").all()
    if active_only:
        qs = qs.filter(is_active=True, product__is_active=True)
    if search:
        qs = qs.filter(
            Q(sku__icontains=search) |
            Q(name__icontains=search) |
            Q(product__name__icontains=search)
        )
    return qs.order_by("product__name", "sku")


def get_total_available(variant_id) -> int:
    """Sum of available qty across all active warehouses."""
    result = (
        WarehouseStock.objects
        .filter(variant_id=variant_id, warehouse__is_active=True)
        .aggregate(total=Sum("available"))
    )
    return result["total"] or 0


def get_low_stock_records(threshold: int | None = None) -> QuerySet:
    """
    All stock records where available <= threshold.
    If threshold is None, uses the per-record low_stock_threshold field.
    """
    qs = WarehouseStock.objects.select_related("variant__product", "warehouse").filter(available__gt=0)
    if threshold is not None:
        return qs.filter(available__lte=threshold)
    # Use each row's own threshold
    from django.db.models import F
    return qs.filter(available__lte=F("low_stock_threshold"))


def get_out_of_stock_records() -> QuerySet:
    return (
        WarehouseStock.objects
        .select_related("variant__product", "warehouse")
        .filter(available__lte=0)
    )


# ─────────────────────────────────────────────────────────────
#  Ledger / History
# ─────────────────────────────────────────────────────────────

def get_ledger_for_variant(
    variant_id,
    warehouse_id=None,
    movement_type: str | None = None,
    limit: int = 100,
) -> QuerySet:
    qs = (
        StockLedger.objects
        .select_related("stock_record__warehouse", "stock_record__variant", "created_by")
        .filter(stock_record__variant_id=variant_id)
    )
    if warehouse_id:
        qs = qs.filter(stock_record__warehouse_id=warehouse_id)
    if movement_type:
        qs = qs.filter(movement_type=movement_type)
    return qs.order_by("-created_at")[:limit]


def get_ledger_for_reference(
    reference_type: str,
    reference_id: str,
) -> QuerySet:
    """All ledger entries for a specific order, return, or exchange."""
    return (
        StockLedger.objects
        .select_related("stock_record__variant", "stock_record__warehouse")
        .filter(reference_type=reference_type, reference_id=reference_id)
        .order_by("-created_at")
    )


# ─────────────────────────────────────────────────────────────
#  Reservations
# ─────────────────────────────────────────────────────────────

def get_active_reservations_for_order(order_id: str) -> QuerySet:
    return (
        StockReservation.objects
        .select_related("stock_record__variant", "stock_record__warehouse")
        .filter(reference_id=order_id, status=ReservationStatus.ACTIVE)
    )


def get_reservation_summary_for_order(order_id: str) -> list[dict]:
    """
    Return a list of dicts with SKU + warehouse + reserved qty for an order.
    Useful for order detail pages.
    """
    reservations = get_active_reservations_for_order(order_id)
    return [
        {
            "sku":       r.stock_record.variant.sku,
            "warehouse": r.stock_record.warehouse.code,
            "quantity":  r.quantity,
            "status":    r.status,
            "expires_at": r.expires_at,
        }
        for r in reservations
    ]


def check_availability(variant_id, quantity: int, warehouse_id=None) -> dict:
    """
    Lightweight availability check without a database lock.
    NOT safe for concurrent order creation — use services.reserve_stock() for that.

    Returns:
        {
            "available": True/False,
            "on_hand":   int,
            "reserved":  int,
            "quantity_available": int,
        }
    """
    stock = get_stock_for_variant(variant_id, warehouse_id)
    if not stock:
        return {"available": False, "on_hand": 0, "reserved": 0, "quantity_available": 0}

    return {
        "available":          stock.available >= quantity,
        "on_hand":            stock.on_hand,
        "reserved":           stock.reserved,
        "quantity_available": stock.available,
    }
