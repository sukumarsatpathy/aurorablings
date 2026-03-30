"""
cart.selectors
~~~~~~~~~~~~~~
Read-only queries for the cart system.
"""

from __future__ import annotations

from decimal import Decimal
from django.db.models import Sum, F, ExpressionWrapper, DecimalField
from core.logging import get_logger

from .models import Cart, CartItem, CartStatus

logger = get_logger(__name__)

# ─────────────────────────────────────────────────────────────
#  Cart retrieval
# ─────────────────────────────────────────────────────────────

def get_cart_for_user(user) -> Cart | None:
    """Return the active cart for an authenticated user."""
    qs = (
        Cart.objects
        .prefetch_related(
            "items__variant__attribute_values__attribute",
            "items__variant__product__media",
        )
        .filter(user=user, status=CartStatus.ACTIVE)
        .order_by("-updated_at", "-created_at")
    )
    try:
        return qs.get()
    except Cart.DoesNotExist:
        return None
    except Cart.MultipleObjectsReturned:
        chosen = qs.first()
        logger.warning(
            "multiple_active_user_carts_detected",
            user_id=str(getattr(user, "id", "")),
            chosen_cart_id=str(chosen.id) if chosen else "",
            active_count=qs.count(),
        )
        return chosen


def get_cart_by_session(session_key: str) -> Cart | None:
    """Return an active, non-expired guest cart by session key."""
    from django.utils import timezone
    qs = (
        Cart.objects
        .prefetch_related(
            "items__variant__attribute_values__attribute",
            "items__variant__product__media",
        )
        .filter(session_key=session_key, status=CartStatus.ACTIVE)
        .order_by("-updated_at", "-created_at")
    )
    try:
        cart = qs.get()
    except Cart.DoesNotExist:
        return None
    except Cart.MultipleObjectsReturned:
        cart = qs.first()
        logger.warning(
            "multiple_active_session_carts_detected",
            session_key=(session_key or "")[:12],
            chosen_cart_id=str(cart.id) if cart else "",
            active_count=qs.count(),
        )

    if not cart:
        return None

    if cart.is_expired:
        cart.status = CartStatus.ABANDONED
        cart.save(update_fields=["status"])
        return None
    return cart


def get_cart_by_id(cart_id) -> Cart | None:
    try:
        return Cart.objects.get(id=cart_id)
    except Cart.DoesNotExist:
        return None


# ─────────────────────────────────────────────────────────────
#  Cart totals
# ─────────────────────────────────────────────────────────────

def calculate_cart_totals(cart: Cart) -> dict:
    """
    Compute all cart totals in one DB round-trip.

    Returns:
        {
            "item_count":        int,    total units
            "line_count":        int,    distinct variants
            "subtotal":          Decimal,
            "original_subtotal": Decimal,  (based on compare_at_price)
            "savings":           Decimal,
            "items": [
                {
                    "id", "variant_id", "sku", "product_name", "product_slug",
                    "variant_name", "quantity", "unit_price",
                    "compare_at_price", "line_total", "is_price_stale",
                    "thumbnail"
                }
            ]
        }
    """
    items = list(
        cart.items
        .select_related(
            "variant__product__category",
        )
        .prefetch_related(
            "variant__attribute_values__attribute",
            "variant__product__media",
        )
    )

    item_count        = sum(i.quantity for i in items)
    subtotal          = sum(i.line_total for i in items)
    original_subtotal = sum(
        (i.compare_at_price or i.unit_price) * i.quantity for i in items
    )
    savings = max(Decimal("0"), original_subtotal - subtotal)

    return {
        "item_count":        item_count,
        "line_count":        len(items),
        "subtotal":          subtotal,
        "original_subtotal": original_subtotal,
        "savings":           savings,
        "items":             [_serialise_item(i) for i in items],
    }


def _serialise_item(item: CartItem) -> dict:
    """Build a lightweight dict for a CartItem — avoids circular import with serializers."""
    variant = item.variant
    product = variant.product

    # Primary image
    media_qs = product.media.all()
    primary  = next((m for m in media_qs if m.is_primary), None) or (media_qs[0] if media_qs else None)
    thumbnail_url = primary.image.url if primary and primary.image else None

    # Attribute label (e.g. "Red / M")
    av_labels = " / ".join(
        av.value for av in variant.attribute_values.all()
    )

    return {
        "id":              str(item.id),
        "variant_id":      str(variant.id),
        "sku":             variant.sku,
        "product_name":    product.name,
        "product_slug":    product.slug,
        "variant_name":    av_labels or variant.name or product.name,
        "quantity":        item.quantity,
        "unit_price":      item.unit_price,
        "compare_at_price": item.compare_at_price,
        "line_total":      item.line_total,
        "is_price_stale":  item.is_price_stale,
        "thumbnail":       thumbnail_url,
    }
