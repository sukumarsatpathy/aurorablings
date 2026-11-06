"""
pos.quick_items
~~~~~~~~~~~~~~~

Selling pieces that have no barcode and no catalogue entry.

A quick item is photographed at the counter with a name, a price and how many
are on hand. It is *not* a Product — it never reaches the website — but a sale of
one is a normal order: the line is an ``OrderItem`` with no variant (the same
shape every order path already handles for a deleted product), priced here from
the server-side record, never from the tablet.

Nothing in this module runs for a sale that has no quick items in it. The
existing catalogue path is called exactly as before, so a barcode-only sale is
unchanged by this feature.
"""

from __future__ import annotations

from decimal import Decimal

import structlog
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.pos.models import POSQuickItem, POSQuickSaleLine

logger = structlog.get_logger(__name__)

ZERO = Decimal("0.00")
CENT = Decimal("0.01")


class QuickItemError(Exception):
    """Raised when a quick item cannot be created, changed or sold as asked."""


# ─────────────────────────────────────────────────────────────
#  The record
# ─────────────────────────────────────────────────────────────

def _store_image(item: POSQuickItem, upload) -> None:
    """Shrink a phone photo to a WebP the till can load on 4G."""
    if not upload:
        return
    try:
        from core.image_optimization import compress_image

        filename, content = compress_image(
            upload, output_dir="", max_width=900, quality=74, file_stem=f"quick-{item.id.hex[:12]}",
        )
        item.image.save(filename.lstrip("/"), content, save=False)
    except Exception:  # an unreadable image must not lose the item
        logger.warning("pos_quick_item_image_compress_failed", item_id=str(item.id), exc_info=True)
        upload.seek(0) if hasattr(upload, "seek") else None
        item.image.save(getattr(upload, "name", "photo.jpg"), upload, save=False)


def _clean(name: str, price, quantity) -> tuple[str, Decimal, int]:
    name = (name or "").strip()
    if not name:
        raise QuickItemError("Give the piece a name.")
    try:
        price = Decimal(str(price)).quantize(CENT)
    except Exception:
        raise QuickItemError("Price must be a number.")
    if price <= ZERO:
        raise QuickItemError("Price must be more than zero.")
    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        raise QuickItemError("Quantity must be a whole number.")
    if quantity < 0:
        raise QuickItemError("Quantity cannot be negative.")
    return name, price, quantity


@transaction.atomic
def create_quick_item(*, name: str, price, quantity=1, image=None, staff=None) -> POSQuickItem:
    name, price, quantity = _clean(name, price, quantity)
    if quantity < 1:
        raise QuickItemError("Quantity must be at least 1.")
    item = POSQuickItem(name=name, price=price, quantity=quantity, created_by=staff)
    _store_image(item, image)
    item.save()
    logger.info("pos_quick_item_created", item_id=str(item.id), price=str(price),
                quantity=quantity, staff=getattr(staff, "id", None))
    return item


@transaction.atomic
def update_quick_item(*, item: POSQuickItem, staff=None, image=None, **changes) -> POSQuickItem:
    """Fix a name, price, count or photo. Past sales keep their own snapshot."""
    item = POSQuickItem.objects.select_for_update().get(pk=item.pk)
    name, price, quantity = _clean(
        changes.get("name", item.name),
        changes.get("price", item.price),
        changes.get("quantity", item.quantity),
    )
    item.name, item.price, item.quantity = name, price, quantity
    if "is_active" in changes:
        item.is_active = bool(changes["is_active"])
    _store_image(item, image)
    item.save()
    logger.info("pos_quick_item_updated", item_id=str(item.id), staff=getattr(staff, "id", None))
    return item


# ─────────────────────────────────────────────────────────────
#  Selling
# ─────────────────────────────────────────────────────────────

def split_lines(items: list[dict]) -> tuple[list[dict], list[dict]]:
    """Separate catalogue lines from quick-item lines, merging repeats."""
    variant_lines: list[dict] = []
    merged: dict[str, int] = {}
    for row in items:
        quick_id = row.get("quick_item_id")
        if quick_id:
            key = str(quick_id)
            merged[key] = merged.get(key, 0) + int(row.get("quantity") or 0)
        else:
            variant_lines.append(row)
    quick_lines = [{"quick_item_id": k, "quantity": q} for k, q in merged.items()]
    return variant_lines, quick_lines


def _load(quick_lines: list[dict], *, lock: bool) -> list[tuple[POSQuickItem, int]]:
    ids = [line["quick_item_id"] for line in quick_lines]
    qs = POSQuickItem.objects.filter(pk__in=ids, is_active=True)
    if lock:
        qs = qs.select_for_update()
    found = {str(i.id): i for i in qs}
    resolved = []
    for line in quick_lines:
        item = found.get(str(line["quick_item_id"]))
        if item is None:
            raise QuickItemError("A quick item on this sale no longer exists or was removed.")
        qty = int(line["quantity"])
        if qty < 1:
            raise QuickItemError("Each line needs a quantity of at least 1.")
        if qty > item.quantity:
            raise QuickItemError(
                f"Only {item.quantity} of “{item.name}” left — {qty} asked for."
            )
        resolved.append((item, qty))
    return resolved


def quick_subtotal(quick_lines: list[dict]) -> tuple[Decimal, list[dict]]:
    """Price quick lines for a quote. Validates stock, persists nothing."""
    total = ZERO
    rows = []
    for item, qty in _load(quick_lines, lock=False):
        line_total = (item.price * qty).quantize(CENT)
        total += line_total
        rows.append({
            "quick_item_id": str(item.id),
            "sku": "",
            "product_name": item.name,
            "variant_name": "",
            "quantity": qty,
            "unit_price": item.price,
            "line_total": line_total,
        })
    return total, rows


def _image_url(item: POSQuickItem) -> str:
    try:
        return str(item.image.url) if item.image else ""
    except Exception:
        return ""


def add_quick_lines(*, order, quick_lines: list[dict]) -> None:
    """
    Put quick items on an order and take them off the shelf.

    Called inside the order-creation transaction. The rows are locked, so two
    tills cannot both sell the last piece.
    """
    from apps.orders.models import OrderItem

    for item, qty in _load(quick_lines, lock=True):
        line_total = (item.price * qty).quantize(CENT)
        order_item = OrderItem.objects.create(
            order=order,
            variant=None,
            sku=f"QUICK-{item.id.hex[:8].upper()}",
            product_name=item.name,
            variant_name="",
            product_snapshot={
                "quick_item_id": str(item.id),
                "product_name": item.name,
                "unit_price": str(item.price),
                "image_url": _image_url(item),
                "source": "pos_quick_item",
            },
            quantity=qty,
            unit_price=item.price,
            line_total=line_total,
            warehouse=order.warehouse,
        )
        POSQuickItem.objects.filter(pk=item.pk).update(quantity=F("quantity") - qty)
        POSQuickSaleLine.objects.create(
            order=order, order_item=order_item, quick_item=item, quantity=qty,
        )


def reprice_order(order, *, payment_method: str) -> None:
    """
    Recompute an order's totals over every line, quick ones included.

    The same surcharge engine and the same inputs ``place_order`` uses, so a sale
    with quick items is taxed exactly as it would be if those pieces were
    catalogue products. Only reached when a sale has quick items in it.
    """
    from apps.surcharge.services import SurchargeContext, calculate_surcharges

    subtotal = sum((i.line_total for i in order.items.all()), ZERO)
    address = order.shipping_address or {}
    try:
        result = calculate_surcharges(SurchargeContext(
            subtotal=subtotal,
            payment_method=payment_method,
            state_code=address.get("state_code", ""),
            pincode=address.get("pincode", ""),
            user_role=order.user.role if order.user_id else "customer",
        ))
        tax, shipping = result.tax_total, result.shipping_total
        discount = result.discount_total
        grand_total = max(ZERO, result.grand_total)
    except Exception as exc:
        logger.warning("surcharge_engine_error", error=str(exc))
        tax = shipping = discount = ZERO
        grand_total = subtotal

    order.subtotal = subtotal
    order.tax_amount = tax
    order.shipping_cost = shipping
    order.discount_amount = discount
    order.grand_total = Decimal(grand_total).quantize(CENT)
    order.save(update_fields=["subtotal", "tax_amount", "shipping_cost", "discount_amount", "grand_total"])


@transaction.atomic
def restock_order(order) -> int:
    """
    Put an abandoned sale's quick items back on the shelf. Safe to call twice.

    Runs from the order-cancelled signal, so a POS void, the stale-order sweeper
    and an admin cancel all return the pieces the same way.
    """
    lines = list(
        POSQuickSaleLine.objects.select_for_update()
        .filter(order=order, restocked_at__isnull=True)
    )
    for line in lines:
        POSQuickItem.objects.filter(pk=line.quick_item_id).update(quantity=F("quantity") + line.quantity)
        line.restocked_at = timezone.now()
        line.save(update_fields=["restocked_at"])
    if lines:
        logger.info("pos_quick_items_restocked", order_id=str(order.id), lines=len(lines))
    return len(lines)


def lines_for_cart(order) -> list[dict]:
    """What "back to cart" refills from, for the quick part of a sale."""
    return [
        {"quick_item_id": str(line.quick_item_id), "quantity": line.quantity}
        for line in order.pos_quick_lines.all()
    ]
