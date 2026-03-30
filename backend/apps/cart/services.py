"""
cart.services
~~~~~~~~~~~~~
All cart mutations.

Key behaviours:
──────────────
1. Guest ↔ User carts
   - get_or_create_user_cart()   → finds or creates an ACTIVE cart for a user
   - get_or_create_guest_cart()  → finds or creates an ACTIVE guest cart by session_key
   - merge_guest_cart()          → on login: folds guest items into user cart

2. add_item()
   - Validates stock availability (non-locking, display-only check)
   - Creates CartItem or increments qty if variant already in cart
   - Snapshots unit_price + compare_at_price from the variant at add time

3. update_item()
   - Re-validates stock for the new quantity
   - Refreshes price snapshot (in case price changed between add and update)

4. remove_item()
   - Hard-deletes the CartItem row

5. clear_cart()
   - Removes all items; cart remains ACTIVE (empty)

6. validate_cart()
   - Runs a full stock check across all items before checkout
   - Returns a list of validation errors (does NOT mutate stock)

7. convert_cart()
   - Marks cart CONVERTED (called by the Order service after reservation)

Stock validation uses inventory.selectors.check_availability() (read-only).
The actual stock reservation happens in inventory.services.reserve_stock(),
called by the Order service at checkout — not here.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from core.exceptions import NotFoundError, ValidationError
from core.logging import get_logger
from apps.inventory.selectors import check_availability

from .models import Cart, CartItem, CartStatus
from .selectors import get_cart_for_user, get_cart_by_session

logger = get_logger(__name__)

_GUEST_CART_TTL_DAYS = 30


# ─────────────────────────────────────────────────────────────
#  Cart creation / retrieval
# ─────────────────────────────────────────────────────────────

def get_or_create_user_cart(user) -> Cart:
    """Return the active user cart, creating one if needed."""
    cart = get_cart_for_user(user)
    if cart:
        return cart

    # Cart.user is OneToOne in this codebase, so historical non-active carts
    # (e.g., converted) must be re-used instead of creating a new row.
    existing = Cart.objects.filter(user=user).first()
    if existing:
        existing.items.all().delete()
        existing.status = CartStatus.ACTIVE
        existing.expires_at = None
        existing.save(update_fields=["status", "expires_at", "updated_at"])
        logger.info("user_cart_reactivated", cart_id=str(existing.id), user_id=str(user.id))
        return existing

    cart = Cart.objects.create(user=user, session_key=None)
    logger.info("cart_created", cart_id=str(cart.id), user_id=str(user.id))
    return cart


def get_or_create_guest_cart(session_key: str) -> Cart:
    """Return the active guest cart for a session key, creating one if needed."""
    if not session_key:
        raise ValidationError("A session key is required for guest carts.")

    cart = get_cart_by_session(session_key)
    if cart:
        return cart

    cart = Cart.objects.create(
        user=None,
        session_key=session_key,
        expires_at=timezone.now() + timedelta(days=_GUEST_CART_TTL_DAYS),
    )
    logger.info("guest_cart_created", cart_id=str(cart.id), session_key=session_key[:8])
    return cart


# ─────────────────────────────────────────────────────────────
#  Merge: guest → user  (on login)
# ─────────────────────────────────────────────────────────────

@transaction.atomic
def merge_guest_cart(*, user, session_key: str) -> Cart:
    """
    Merge a guest cart into the user's active cart when they log in.

    Merge strategy (per item):
      - If variant already in user cart → take the HIGHER quantity.
      - If variant only in guest cart   → move item to user cart.
      - Price snapshots from guest cart overwrite user cart (fresher).

    After merge:
      - Guest cart is marked MERGED.
      - User cart is returned.
    """
    guest_cart = get_cart_by_session(session_key)
    if not guest_cart or not guest_cart.items.exists():
        # Nothing to merge
        return get_or_create_user_cart(user)

    user_cart = get_or_create_user_cart(user)
    guest_items = list(guest_cart.items.select_related("variant"))

    for guest_item in guest_items:
        try:
            user_item = CartItem.objects.get(cart=user_cart, variant=guest_item.variant)
            # Keep the higher quantity
            if guest_item.quantity > user_item.quantity:
                user_item.quantity = guest_item.quantity
            # Refresh price snapshot from guest (more recent)
            user_item.unit_price      = guest_item.unit_price
            user_item.compare_at_price = guest_item.compare_at_price
            user_item.save(update_fields=["quantity", "unit_price", "compare_at_price", "updated_at"])
        except CartItem.DoesNotExist:
            # Move item to user cart
            guest_item.cart = user_cart
            guest_item.save(update_fields=["cart"])

    guest_cart.status = CartStatus.MERGED
    guest_cart.save(update_fields=["status"])
    user_cart.touch()

    logger.info(
        "carts_merged",
        guest_cart_id=str(guest_cart.id),
        user_cart_id=str(user_cart.id),
        user_id=str(user.id),
        items_merged=len(guest_items),
    )
    return user_cart


# ─────────────────────────────────────────────────────────────
#  Add item
# ─────────────────────────────────────────────────────────────

@transaction.atomic
def add_item(
    *,
    cart: Cart,
    variant_id,
    quantity: int,
    warehouse_id=None,
) -> CartItem:
    """
    Add a variant to the cart or increment its quantity.

    Stock check: availability is validated here (non-locking).
    Actual reservation happens at checkout.

    Raises:
        NotFoundError: variant does not exist or is inactive.
        ValidationError: insufficient stock.
    """
    _validate_quantity(quantity)
    variant = _get_active_variant(variant_id)

    # How much is already in cart?
    existing_qty = 0
    try:
        existing_item = CartItem.objects.get(cart=cart, variant=variant)
        existing_qty  = existing_item.quantity
    except CartItem.DoesNotExist:
        existing_item = None

    total_requested = existing_qty + quantity
    _validate_stock(variant, total_requested, warehouse_id)

    if existing_item:
        existing_item.quantity   = total_requested
        existing_item.unit_price = variant.effective_price   # refresh snapshot on add
        existing_item.compare_at_price = variant.display_compare_at_price
        existing_item.save(update_fields=["quantity", "unit_price", "compare_at_price", "updated_at"])
        cart_item = existing_item
        logger.info("cart_item_incremented", cart_id=str(cart.id), sku=variant.sku, qty=total_requested)
    else:
        cart_item = CartItem.objects.create(
            cart=cart,
            variant=variant,
            quantity=quantity,
            unit_price=variant.effective_price,
            compare_at_price=variant.display_compare_at_price,
        )
        logger.info("cart_item_added", cart_id=str(cart.id), sku=variant.sku, qty=quantity)

    cart.touch()
    return cart_item


# ─────────────────────────────────────────────────────────────
#  Update item
# ─────────────────────────────────────────────────────────────

@transaction.atomic
def update_item(
    *,
    cart: Cart,
    item_id,
    quantity: int,
    warehouse_id=None,
) -> CartItem:
    """
    Set a cart item's quantity to an explicit value.
    quantity=0 is rejected — use remove_item() instead.
    Refreshes the price snapshot.
    """
    _validate_quantity(quantity)

    try:
        item = CartItem.objects.select_related("variant").get(id=item_id, cart=cart)
    except CartItem.DoesNotExist:
        raise NotFoundError("Cart item not found.")

    _validate_stock(item.variant, quantity, warehouse_id)

    # Refresh price snapshot on update
    item.quantity        = quantity
    item.unit_price      = item.variant.effective_price
    item.compare_at_price = item.variant.display_compare_at_price
    item.save(update_fields=["quantity", "unit_price", "compare_at_price", "updated_at"])
    cart.touch()

    logger.info(
        "cart_item_updated",
        cart_id=str(cart.id),
        item_id=str(item.id),
        sku=item.variant.sku,
        qty=quantity,
    )
    return item


# ─────────────────────────────────────────────────────────────
#  Remove item
# ─────────────────────────────────────────────────────────────

def remove_item(*, cart: Cart, item_id) -> None:
    """Remove a single item from the cart."""
    try:
        item = CartItem.objects.get(id=item_id, cart=cart)
    except CartItem.DoesNotExist:
        raise NotFoundError("Cart item not found.")

    sku = item.variant.sku
    item.delete()
    cart.touch()
    logger.info("cart_item_removed", cart_id=str(cart.id), sku=sku)


# ─────────────────────────────────────────────────────────────
#  Clear cart
# ─────────────────────────────────────────────────────────────

def clear_cart(*, cart: Cart) -> None:
    """Remove ALL items — cart remains ACTIVE (empty)."""
    count = cart.items.count()
    cart.items.all().delete()
    cart.touch()
    logger.info("cart_cleared", cart_id=str(cart.id), items_removed=count)


# ─────────────────────────────────────────────────────────────
#  Validate cart (pre-checkout)
# ─────────────────────────────────────────────────────────────

def validate_cart(*, cart: Cart, warehouse_id=None) -> list[dict]:
    """
    Run a full stock + price check across every item.
    Returns a list of error dicts — empty list means cart is valid.

    Does NOT mutate stock (use inventory.services.reserve_stock at checkout).

    Example error:
        {
            "item_id": "...",
            "sku": "SKU-001",
            "issue": "insufficient_stock",
            "message": "Only 2 units available.",
            "available": 2,
            "requested": 5,
        }
    """
    errors = []
    items  = cart.items.select_related("variant").all()

    for item in items:
        variant = item.variant

        # ── 1. Variant still active? ──────────────────────────
        if not variant.is_active:
            errors.append({
                "item_id":  str(item.id),
                "sku":      variant.sku,
                "issue":    "variant_inactive",
                "message":  f"'{variant.sku}' is no longer available.",
            })
            continue

        # ── 2. Stock available? ───────────────────────────────
        avail = check_availability(variant.id, item.quantity, warehouse_id)
        if not avail["available"]:
            errors.append({
                "item_id":   str(item.id),
                "sku":       variant.sku,
                "issue":     "insufficient_stock",
                "message":   f"Only {avail['quantity_available']} unit(s) of '{variant.sku}' available.",
                "available": avail["quantity_available"],
                "requested": item.quantity,
            })

        # ── 3. Price changed since snapshot? ──────────────────
        if item.is_price_stale:
            errors.append({
                "item_id":       str(item.id),
                "sku":           variant.sku,
                "issue":         "price_changed",
                "message":       f"Price for '{variant.sku}' has changed.",
                "snapshot_price": str(item.unit_price),
                "current_price":  str(variant.effective_price),
            })

    if errors:
        logger.warning(
            "cart_validation_failed",
            cart_id=str(cart.id),
            error_count=len(errors),
        )
    return errors


# ─────────────────────────────────────────────────────────────
#  Convert cart (called by Order service at checkout)
# ─────────────────────────────────────────────────────────────

def convert_cart(*, cart: Cart) -> None:
    """Mark cart as CONVERTED after a successful order placement."""
    cart.status = CartStatus.CONVERTED
    cart.save(update_fields=["status", "updated_at"])
    logger.info("cart_converted", cart_id=str(cart.id))


# ─────────────────────────────────────────────────────────────
#  Private helpers
# ─────────────────────────────────────────────────────────────

def _validate_quantity(quantity: int) -> None:
    if not isinstance(quantity, int) or quantity < 1:
        raise ValidationError("Quantity must be a positive integer.")

    if quantity > 100:
        raise ValidationError("Maximum quantity per item is 100.")


def _get_active_variant(variant_id):
    from apps.catalog.models import ProductVariant
    try:
        variant = (
            ProductVariant.objects
            .select_related("product")
            .prefetch_related("attribute_values__attribute")
            .get(id=variant_id, is_active=True)
        )
    except ProductVariant.DoesNotExist:
        raise NotFoundError("Product variant not found or inactive.")

    if not variant.product.is_active:
        raise NotFoundError("Product is no longer available.")
    return variant


def _validate_stock(variant, quantity: int, warehouse_id=None) -> None:
    """Non-locking stock check — for display guards during cart operations."""
    avail = check_availability(variant.id, quantity, warehouse_id)
    if not avail["available"]:
        qty = avail["quantity_available"]
        msg = (
            f"Only {qty} unit(s) of '{variant.sku}' available."
            if qty > 0
            else f"'{variant.sku}' is out of stock."
        )
        raise ValidationError(msg, extra={
            "sku":       variant.sku,
            "requested": quantity,
            "available": qty,
        })
