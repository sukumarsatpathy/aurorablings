"""
orders.services
~~~~~~~~~~~~~~~

Core flows:
───────────

1. place_order(cart, user/guest_email, shipping_address, ...)
   ├─ validate_cart()                         check stock + price
   ├─ reserve_stock() per item               lock inventory
   ├─ build Order + OrderItems (snapshots)
   ├─ convert_cart() → CONVERTED
   └─ log DRAFT → PLACED transition

2. transition_order(order, new_status, changed_by, notes)
   ├─ guards STATE_TRANSITIONS
   ├─ updates status + timestamp fields
   └─ logs to OrderStatusHistory

3. cancel_order(order, changed_by, reason)
   ├─ guards cancellable statuses
   ├─ release_reservation() per item
   └─ transitions → CANCELLED

4. mark_paid(order, payment_reference, method, changed_by)
   ├─ validates PLACED status
   ├─ records payment fields
   └─ transitions → PAID

5. mark_shipped(order, tracking_number, carrier, changed_by)
   └─ transitions PAID/PROCESSING → SHIPPED

6. mark_delivered / mark_completed
   → straight transitions with timestamp update
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from urllib.parse import urlparse

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from core.exceptions import ValidationError, ConflictError
from core.logging import get_logger
from audit.models import ActorType, AuditAction
from audit.services.activity_logger import log_activity

from apps.cart.services import validate_cart as cart_validate_service, convert_cart
from apps.cart.models import Cart, CartItem
from apps.catalog.models import ProductVariant
from apps.inventory.services import reserve_stock, release_reservation, commit_reservation
from apps.inventory.selectors import get_default_warehouse
from apps.pricing.services import PricingService
from apps.pricing.coupons.services import CouponService
from apps.surcharge.services import SurchargeContext, CartItemContext, calculate_surcharges
from apps.features import services as feature_services

from .models import (
    Order, OrderItem, OrderStatusHistory,
    OrderStatus, PaymentStatus, PaymentMethod,
    STATE_TRANSITIONS, CANCELLABLE_STATUSES,
)

logger = get_logger(__name__)

ONLINE_PAYMENT_METHODS = {
    PaymentMethod.CASHFREE,
    PaymentMethod.RAZORPAY,
    PaymentMethod.PHONEPE,
    PaymentMethod.STRIPE,
    PaymentMethod.UPI,
}


def _is_private_host(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host in {"", "localhost", "127.0.0.1", "0.0.0.0", "backend", "db", "redis"}


def _get_public_base_url() -> str:
    frontend = str(feature_services.get_setting("site.frontend_url", default="https://aurorablings.com") or "https://aurorablings.com").rstrip("/")
    backend = str(feature_services.get_setting("site.backend_url", default=getattr(settings, "BACKEND_URL", "") or "")).rstrip("/")
    if backend and not _is_private_host(backend):
        return backend
    if frontend and not _is_private_host(frontend):
        return frontend
    return "https://aurorablings.com"


def _to_public_url(url_or_path: str) -> str:
    value = str(url_or_path or "").strip()
    if not value:
        return ""
    if value.startswith("http://") or value.startswith("https://"):
        return value if not _is_private_host(value) else ""
    if value.startswith("/"):
        return f"{_get_public_base_url()}{value}"
    return f"{_get_public_base_url()}/{value.lstrip('/')}"


def _build_order_items_for_email(order: Order) -> list[dict]:
    rows = []
    for item in order.items.select_related("variant__product").all():
        snapshot = item.product_snapshot or {}
        image_url = str(snapshot.get("image_url", "") or "")

        if not image_url and item.variant_id and item.variant and item.variant.product_id:
            media = item.variant.product.media.filter(is_primary=True).first() or item.variant.product.media.first()
            if media and getattr(media, "image", None):
                image_url = str(media.image.url or "")

        rows.append(
            {
                "name": item.product_name,
                "quantity": item.quantity,
                "total_price": str(item.line_total),
                "image": _to_public_url(image_url),
            }
        )
    return rows


def build_order_confirmation_email_context(*, order: Order, customer_name: str = "Customer") -> dict:
    return {
        "order_number": order.order_number,
        "order_id": order.order_number,
        "subtotal": str(order.subtotal),
        "shipping": str(order.shipping_cost),
        "shipping_cost": str(order.shipping_cost),
        "total": str(order.grand_total),
        "grand_total": str(order.grand_total),
        "currency": order.currency,
        "item_count": str(order.items.count()),
        "items": _build_order_items_for_email(order),
        "user_name": customer_name,
        "customer_name": customer_name,
        "order_url": f"/account/orders/{order.id}",
    }


def _resolve_order_recipient(order: Order) -> tuple[str, str]:
    recipient_email = (order.user.email if order.user_id and order.user else (order.guest_email or "")).strip()
    shipping_name = ""
    if isinstance(order.shipping_address, dict):
        shipping_name = str(order.shipping_address.get("full_name", "") or "").strip()
    customer_name = (
        (order.user.get_full_name().strip() if order.user_id and order.user else "")
        or shipping_name
        or (recipient_email.split("@")[0] if recipient_email else "")
        or "Customer"
    )
    return recipient_email, customer_name


def _queue_order_confirmation_email(*, order: Order) -> None:
    recipient_email, customer_name = _resolve_order_recipient(order)
    if not recipient_email:
        return

    from apps.invoices.services.invoice_service import InvoiceService
    from apps.notifications.events import NotificationEvent
    from apps.notifications.tasks import trigger_event_task

    trigger_event_task.delay(
        event=NotificationEvent.ORDER_CREATED,
        context={
            **build_order_confirmation_email_context(
                order=order,
                customer_name=customer_name,
            ),
            "invoice_url": InvoiceService.build_public_invoice_url(order_id=str(order.id)),
            "payment_status": order.payment_status,
        },
        user_id=str(order.user.id) if order.user else None,
        recipient_email=recipient_email,
    )


@transaction.atomic
def create_admin_order(
    *,
    user=None,
    guest_email: str = "",
    status: str = OrderStatus.PLACED,
    payment_status: str = PaymentStatus.PENDING,
    payment_method: str = PaymentMethod.COD,
    shipping_address: dict | None = None,
    billing_address: dict | None = None,
    subtotal: Decimal = Decimal("0"),
    discount_amount: Decimal = Decimal("0"),
    shipping_cost: Decimal = Decimal("0"),
    tax_amount: Decimal = Decimal("0"),
    grand_total: Decimal = Decimal("0"),
    currency: str = "INR",
    notes: str = "",
    internal_notes: str = "",
    changed_by=None,
) -> Order:
    shipping_address = shipping_address or {}
    billing_address = billing_address or shipping_address
    placed_at = timezone.now() if status in {OrderStatus.PLACED, OrderStatus.PAID, OrderStatus.PROCESSING, OrderStatus.SHIPPED, OrderStatus.DELIVERED, OrderStatus.COMPLETED, OrderStatus.REFUNDED} else None
    paid_at = timezone.now() if status in {OrderStatus.PAID, OrderStatus.PROCESSING, OrderStatus.SHIPPED, OrderStatus.DELIVERED, OrderStatus.COMPLETED, OrderStatus.REFUNDED} else None
    shipped_at = timezone.now() if status in {OrderStatus.SHIPPED, OrderStatus.DELIVERED, OrderStatus.COMPLETED, OrderStatus.REFUNDED} else None
    delivered_at = timezone.now() if status in {OrderStatus.DELIVERED, OrderStatus.COMPLETED, OrderStatus.REFUNDED} else None
    cancelled_at = timezone.now() if status == OrderStatus.CANCELLED else None

    order = Order.objects.create(
        user=user,
        guest_email=guest_email,
        status=status or OrderStatus.DRAFT,
        payment_status=payment_status,
        payment_method=payment_method,
        shipping_address=shipping_address,
        billing_address=billing_address,
        subtotal=subtotal,
        discount_amount=discount_amount,
        shipping_cost=shipping_cost,
        tax_amount=tax_amount,
        grand_total=grand_total,
        currency=currency or "INR",
        notes=notes,
        internal_notes=internal_notes,
        placed_at=placed_at,
        paid_at=paid_at,
        shipped_at=shipped_at,
        delivered_at=delivered_at,
        cancelled_at=cancelled_at,
    )
    if status and status != OrderStatus.DRAFT:
        OrderStatusHistory.objects.create(
            order=order,
            from_status=OrderStatus.DRAFT,
            to_status=status,
            changed_by=changed_by,
            notes="Created from admin panel.",
        )
    return order


@transaction.atomic
def update_admin_order(
    *,
    order: Order,
    changed_by=None,
    **fields,
) -> Order:
    mutable_fields = {
        "payment_status", "payment_method", "shipping_address", "billing_address",
        "subtotal", "discount_amount", "shipping_cost", "tax_amount",
        "grand_total", "currency", "notes", "internal_notes",
        "tracking_number", "shipping_carrier",
    }
    for key, value in fields.items():
        if key in mutable_fields:
            setattr(order, key, value)
    order.save()

    new_status = fields.get("status")
    if new_status and new_status != order.status:
        _apply_transition(
            order=order,
            new_status=new_status,
            changed_by=changed_by,
            notes="Status updated from admin panel.",
        )
    return order


@transaction.atomic
def delete_admin_order(*, order: Order) -> None:
    if order.status in {OrderStatus.PAID, OrderStatus.SHIPPED, OrderStatus.DELIVERED, OrderStatus.COMPLETED}:
        raise ConflictError("Paid or fulfilled orders cannot be deleted.")
    order.delete()


@transaction.atomic
def calculate_admin_order_pricing(
    *,
    items: list[dict],
    payment_method: str = PaymentMethod.COD,
    shipping_address: dict | None = None,
    coupon_code: str = "",
    user=None,
) -> dict:
    """
    Calculate totals for admin-created orders using the same coupon and surcharge engines.
    Does not persist order data.
    """
    temp_cart, cart_items = _build_temp_cart_from_items(items)
    try:
        pricing = PricingService.calculate(
            cart=temp_cart,
            coupon_code=(coupon_code or "").strip() or None,
            user=user,
        )
        coupon_discount = pricing["discount"]
        subtotal = pricing["subtotal"]

        shipping_address = shipping_address or {}
        surcharge_ctx = SurchargeContext(
            subtotal=subtotal,
            items=[
                CartItemContext(
                    variant_id=str(ci.variant.id),
                    category_id=str(ci.variant.product.category_id),
                    quantity=ci.quantity,
                    unit_price=ci.unit_price,
                    weight_grams=ci.variant.weight_grams or 0,
                )
                for ci in cart_items
            ],
            payment_method=payment_method,
            state_code=shipping_address.get("state_code", ""),
            pincode=shipping_address.get("pincode", ""),
            user_role=user.role if user else "customer",
        )
        surcharge_result = calculate_surcharges(surcharge_ctx)

        tax_amount = surcharge_result.tax_total
        shipping_cost = surcharge_result.shipping_total
        surcharge_discount = surcharge_result.discount_total
        discount_total = surcharge_discount + coupon_discount
        grand_total = max(Decimal("0"), surcharge_result.grand_total - coupon_discount)

        return {
            "subtotal": subtotal,
            "discount_amount": discount_total,
            "shipping_cost": shipping_cost,
            "tax_amount": tax_amount,
            "grand_total": grand_total,
            "coupon": pricing.get("coupon"),
            "breakdown": surcharge_result.as_dict().get("breakdown", []),
            "items": [
                {
                    "variant_id": str(ci.variant.id),
                    "sku": ci.variant.sku,
                    "product_name": ci.variant.product.name,
                    "variant_name": ci.variant.name or ci.variant.sku,
                    "quantity": ci.quantity,
                    "unit_price": ci.unit_price,
                    "line_total": ci.line_total,
                }
                for ci in cart_items
            ],
        }
    finally:
        temp_cart.delete()


@transaction.atomic
def create_admin_order_from_items(
    *,
    items: list[dict],
    user=None,
    guest_email: str = "",
    shipping_address: dict | None = None,
    billing_address: dict | None = None,
    payment_method: str = PaymentMethod.COD,
    coupon_code: str = "",
    status: str = OrderStatus.PLACED,
    notes: str = "",
    warehouse_id=None,
    changed_by=None,
) -> Order:
    """
    Persist an admin-created order by building a temporary cart and reusing place_order flow.
    """
    temp_cart, _ = _build_temp_cart_from_items(items)
    try:
        order = place_order(
            cart=temp_cart,
            shipping_address=shipping_address or {},
            billing_address=billing_address or shipping_address or {},
            payment_method=payment_method,
            coupon_code=(coupon_code or "").strip(),
            notes=notes,
            user=user,
            guest_email=guest_email,
            warehouse_id=warehouse_id,
            changed_by=changed_by,
        )
        return _advance_admin_order_status(order=order, target_status=status, changed_by=changed_by)
    finally:
        # place_order converts the cart; cleanup temporary admin cart rows afterwards.
        Cart.objects.filter(id=temp_cart.id).delete()


# ─────────────────────────────────────────────────────────────
#  1.  Place Order  (Cart → Order)
# ─────────────────────────────────────────────────────────────

@transaction.atomic
def place_order(
    *,
    cart,
    shipping_address: dict,
    billing_address: dict | None = None,
    payment_method: str = PaymentMethod.COD,
    shipping_cost: Decimal = Decimal("0"),
    coupon_code: str = "",
    notes: str = "",
    user=None,
    guest_email: str = "",
    warehouse_id=None,
    changed_by=None,
) -> Order:
    """
    Convert a validated cart into a placed order.

    Steps:
      1. Run full cart validation (stock + price)
      2. Resolve warehouse
      3. Reserve stock for each item (SELECT FOR UPDATE)
      4. Build Order + OrderItems with snapshots
      5. Mark cart as CONVERTED
      6. Log DRAFT → PLACED transition

    Raises:
        ValidationError — if cart is empty or has validation errors
        ConflictError   — if stock reservation fails for any item
    """
    # ── 1. Validate ───────────────────────────────────────────
    if not cart.items.exists():
        raise ValidationError("Cannot place an order from an empty cart.")

    errors = cart_validate_service(cart=cart, warehouse_id=warehouse_id)
    if errors:
        raise ValidationError(
            "Cart validation failed. Resolve issues before placing the order.",
            extra={"cart_errors": errors},
        )

    # ── 2. Resolve warehouse ──────────────────────────────────
    warehouse = None
    if warehouse_id:
        from apps.inventory.selectors import get_warehouse_by_id
        warehouse = get_warehouse_by_id(warehouse_id)
        if not warehouse:
            raise ValidationError("Selected warehouse does not exist.")
    if not warehouse:
        warehouse = get_default_warehouse()
    if not warehouse:
        raise ValidationError(
            "No active default warehouse is configured. Please contact support.",
            extra={"warehouse": ["No active default warehouse found."]},
        )

    # ── 3. Build Order (DRAFT) ────────────────────────────────
    items = list(cart.items.select_related(
        "variant__product__category",
    ).prefetch_related("variant__attribute_values__attribute", "variant__product__media"))

    subtotal = sum(i.line_total for i in items)

    coupon_discount = Decimal("0")
    normalised_coupon_code = (coupon_code or "").strip()
    if normalised_coupon_code:
        pricing = PricingService.calculate(
            cart=cart,
            coupon_code=normalised_coupon_code,
            user=user,
        )
        coupon_discount = pricing["discount"]

    # ── Run surcharge engine ──────────────────────────────────
    # Computes tax, shipping, and fee rules from the DB.
    # We pass the cart directly; item snapshots are not yet committed.
    try:
        from apps.surcharge.services import SurchargeContext, calculate_surcharges
        surcharge_ctx = SurchargeContext(
            subtotal=subtotal,
            payment_method=payment_method,
            state_code=shipping_address.get("state_code", ""),
            pincode=shipping_address.get("pincode", ""),
            user_role=user.role if user else "customer",
        )
        surcharge_result = calculate_surcharges(surcharge_ctx)
        tax_amount    = surcharge_result.tax_total
        shipping_cost = surcharge_result.shipping_total
        fee_total     = surcharge_result.fee_total
        discount_total = surcharge_result.discount_total + coupon_discount
        grand_total   = max(Decimal("0"), surcharge_result.grand_total - coupon_discount)
    except Exception as exc:
        logger.warning("surcharge_engine_error", error=str(exc))
        tax_amount     = Decimal("0")
        fee_total      = Decimal("0")
        discount_total = coupon_discount
        grand_total    = max(Decimal("0"), (subtotal + shipping_cost + tax_amount) - coupon_discount)

    billing_address = billing_address or shipping_address

    order = Order.objects.create(
        user=user,
        guest_email=guest_email,
        status=OrderStatus.DRAFT,
        payment_method=payment_method,
        payment_status=PaymentStatus.PENDING,
        shipping_address=shipping_address,
        billing_address=billing_address,
        subtotal=subtotal,
        coupon_code=normalised_coupon_code,
        discount_amount=discount_total,
        shipping_cost=shipping_cost,
        tax_amount=tax_amount,
        grand_total=grand_total,
        notes=notes,
        warehouse=warehouse,
        cart_id_snapshot=cart.id,
    )

    # ── 4. Create OrderItems + reserve stock ──────────────────
    for cart_item in items:
        variant = cart_item.variant
        av_labels = " / ".join(av.value for av in variant.attribute_values.all())

        # Product snapshot — stable historical record
        media = variant.product.media.filter(is_primary=True).first() or variant.product.media.first()
        image_url = str(media.image.url or "") if media and getattr(media, "image", None) else ""
        product_snapshot = {
            "product_id":   str(variant.product.id),
            "variant_id":   str(variant.id),
            "sku":          variant.sku,
            "product_name": variant.product.name,
            "variant_name": av_labels or variant.name,
            "category":     variant.product.category.name,
            "unit_price":   str(cart_item.unit_price),
            "weight_grams": variant.weight_grams,
            "image_url":    image_url,
        }

        OrderItem.objects.create(
            order=order,
            variant=variant,
            sku=variant.sku,
            product_name=variant.product.name,
            variant_name=av_labels or variant.name or variant.sku,
            product_snapshot=product_snapshot,
            quantity=cart_item.quantity,
            unit_price=cart_item.unit_price,
            compare_at_price=cart_item.compare_at_price,
            line_total=cart_item.line_total,
            warehouse=warehouse,
        )

        # Reserve stock — raises InsufficientStockError if unavailable
        reserve_stock(
            variant_id=variant.id,
            warehouse_id=warehouse.id if warehouse else None,
            quantity=cart_item.quantity,
            order_id=str(order.id),
            created_by=changed_by or user,
        )

    # ── 5. Convert cart ───────────────────────────────────────
    convert_cart(cart=cart)

    if normalised_coupon_code and coupon_discount > 0:
        CouponService.record_usage(
            coupon_code=normalised_coupon_code,
            user=user,
            cart=cart,
            order=order,
            discount_amount=coupon_discount,
        )

    # ── 6. Transition DRAFT → PLACED ─────────────────────────
    _apply_transition(
        order=order,
        new_status=OrderStatus.PLACED,
        changed_by=changed_by or user,
        notes="Order placed from cart.",
    )

    logger.info(
        "order_placed",
        order_id=str(order.id),
        order_number=order.order_number,
        grand_total=str(grand_total),
        item_count=len(items),
        user_id=str(user.id) if user else "guest",
    )

    try:
        from apps.invoices.tasks import generate_invoice_task

        generate_invoice_task.delay(str(order.id))
    except Exception:
        pass

    # Queue order confirmation immediately only for offline flows.
    if payment_method not in ONLINE_PAYMENT_METHODS:
        try:
            _queue_order_confirmation_email(order=order)
        except Exception:
            pass   # notifications must never block order placement

    return order


# ─────────────────────────────────────────────────────────────
#  2.  Generic status transition
# ─────────────────────────────────────────────────────────────

@transaction.atomic
def transition_order(
    *,
    order: Order,
    new_status: str,
    changed_by=None,
    notes: str = "",
) -> Order:
    """
    Move an order to `new_status` if the transition is valid.
    All callers (mark_paid, mark_shipped, etc.) use this internally.
    """
    return _apply_transition(
        order=order,
        new_status=new_status,
        changed_by=changed_by,
        notes=notes,
    )


# ─────────────────────────────────────────────────────────────
#  3.  Cancel order
# ─────────────────────────────────────────────────────────────

@transaction.atomic
def cancel_order(
    *,
    order: Order,
    changed_by=None,
    reason: str = "Order cancelled.",
) -> Order:
    """
    Cancel an order and release its stock reservations.
    Only allowed from DRAFT, PLACED, PAID, PROCESSING.
    """
    if not order.is_cancellable:
        raise ConflictError(
            f"Order '{order.order_number}' cannot be cancelled from status '{order.status}'."
        )

    # Release all active stock reservations for this order
    release_reservation(
        order_id=str(order.id),
        notes=f"Reservation released — order cancelled. {reason}",
        created_by=changed_by,
    )

    _apply_transition(
        order=order,
        new_status=OrderStatus.CANCELLED,
        changed_by=changed_by,
        notes=reason,
    )
    logger.info(
        "order_cancelled",
        order_id=str(order.id),
        order_number=order.order_number,
        reason=reason,
    )
    return order


# ─────────────────────────────────────────────────────────────
#  4.  Mark paid
# ─────────────────────────────────────────────────────────────

@transaction.atomic
def mark_paid(
    *,
    order: Order,
    payment_reference: str = "",
    payment_method: str | None = None,
    changed_by=None,
) -> Order:
    """Record payment and advance order to PAID."""
    was_paid = order.payment_status == PaymentStatus.PAID
    order.payment_status    = PaymentStatus.PAID
    order.payment_reference = payment_reference
    order.paid_at           = timezone.now()
    if payment_method:
        order.payment_method = payment_method
    order.save(update_fields=["payment_status", "payment_reference", "paid_at", "payment_method"])

    _apply_transition(
        order=order,
        new_status=OrderStatus.PAID,
        changed_by=changed_by,
        notes=f"Payment received. Ref: {payment_reference}",
    )
    logger.info(
        "order_paid",
        order_id=str(order.id),
        order_number=order.order_number,
        payment_reference=payment_reference,
    )

    # Shipping sync is async and provider-driven; never block payment confirmation.
    try:
        from apps.shipping import services as shipping_services
        if shipping_services.is_auto_create_enabled():
            from apps.shipping.tasks import create_shipment_for_order

            create_shipment_for_order.delay(str(order.id))
    except Exception:
        pass

    if not was_paid:
        try:
            _queue_order_confirmation_email(order=order)
        except Exception:
            pass
    return order


# ─────────────────────────────────────────────────────────────
#  5.  Mark shipped (commits stock reservation)
# ─────────────────────────────────────────────────────────────

@transaction.atomic
def mark_shipped(
    *,
    order: Order,
    tracking_number: str = "",
    shipping_carrier: str = "",
    changed_by=None,
) -> Order:
    """
    Mark order as shipped:
      - Commits stock reservations (on_hand deducted physically)
      - Records tracking info
    """
    order.tracking_number  = tracking_number
    order.shipping_carrier = shipping_carrier
    order.shipped_at       = timezone.now()
    order.save(update_fields=["tracking_number", "shipping_carrier", "shipped_at"])

    # Commit reservations → reduces on_hand in StockLedger
    commit_reservation(
        order_id=str(order.id),
        notes=f"Order shipped. Tracking: {tracking_number}",
        created_by=changed_by,
    )

    _apply_transition(
        order=order,
        new_status=OrderStatus.SHIPPED,
        changed_by=changed_by,
        notes=f"Shipped via {shipping_carrier}. Tracking: {tracking_number}",
    )
    logger.info(
        "order_shipped",
        order_id=str(order.id),
        order_number=order.order_number,
        tracking=tracking_number,
    )

    # Fire ORDER_SHIPPED notification (async, non-blocking)
    try:
        from apps.notifications.tasks import trigger_event_task
        from apps.notifications.events import NotificationEvent
        from apps.invoices.services.invoice_service import InvoiceService
        trigger_event_task.delay(
            event=NotificationEvent.ORDER_SHIPPED,
            context={
                "order_number":    order.order_number,
                "tracking_number": tracking_number,
                "carrier":         shipping_carrier,
                "user_name":       order.user.get_full_name() if order.user else "Customer",
                "customer_name":   order.user.get_full_name() if order.user else "Customer",
                "grand_total":     str(order.grand_total),
                "currency": order.currency,
                "tracking_url": getattr(getattr(order, "shipment", None), "tracking_url", ""),
                "shipment_status": order.status,
                "invoice_url": InvoiceService.build_public_invoice_url(order_id=str(order.id)),
            },
            user_id=str(order.user.id) if order.user else None,
            recipient_email=order.guest_email or "",
        )
    except Exception:
        pass

    return order


# ─────────────────────────────────────────────────────────────
#  6.  Mark delivered / completed
# ─────────────────────────────────────────────────────────────

@transaction.atomic
def mark_delivered(*, order: Order, changed_by=None) -> Order:
    order.delivered_at = timezone.now()
    order.save(update_fields=["delivered_at"])
    order = _apply_transition(
        order=order,
        new_status=OrderStatus.DELIVERED,
        changed_by=changed_by,
        notes="Delivery confirmed.",
    )
    try:
        from apps.notifications.tasks import trigger_event_task
        from apps.notifications.events import NotificationEvent
        from apps.invoices.services.invoice_service import InvoiceService

        trigger_event_task.delay(
            event=NotificationEvent.ORDER_DELIVERED,
            context={
                "order_number": order.order_number,
                "user_name": order.user.get_full_name() if order.user else "Customer",
                "customer_name": order.user.get_full_name() if order.user else "Customer",
                "grand_total": str(order.grand_total),
                "currency": order.currency,
                "invoice_url": InvoiceService.build_public_invoice_url(order_id=str(order.id)),
                "order_url": "/account/orders",
            },
            user_id=str(order.user.id) if order.user else None,
            recipient_email=order.guest_email or "",
        )
    except Exception:
        pass
    return order


@transaction.atomic
def mark_completed(*, order: Order, changed_by=None, notes: str = "") -> Order:
    completed_order = _apply_transition(
        order=order,
        new_status=OrderStatus.COMPLETED,
        changed_by=changed_by,
        notes=notes or "Order completed.",
    )
    # A completed order should never remain in pending payment state.
    if completed_order.payment_status == PaymentStatus.PENDING:
        completed_order.payment_status = PaymentStatus.PAID
        completed_order.paid_at = completed_order.paid_at or timezone.now()
        completed_order.save(update_fields=["payment_status", "paid_at", "updated_at"])
    return completed_order


# ─────────────────────────────────────────────────────────────
#  7.  Refund
# ─────────────────────────────────────────────────────────────

@transaction.atomic
def mark_refunded(
    *,
    order: Order,
    reason: str = "",
    changed_by=None,
) -> Order:
    order.payment_status = PaymentStatus.REFUNDED
    order.save(update_fields=["payment_status"])
    if order.status == OrderStatus.REFUNDED:
        return order
    return _apply_transition(
        order=order,
        new_status=OrderStatus.REFUNDED,
        changed_by=changed_by,
        notes=reason or "Refund issued.",
    )


@transaction.atomic
def mark_partially_refunded(
    *,
    order: Order,
    reason: str = "",
    changed_by=None,
) -> Order:
    """
    Mark an order as partially refunded without closing it as fully refunded.
    """
    order.payment_status = PaymentStatus.PARTIALLY_REFUNDED
    order.save(update_fields=["payment_status"])
    if order.status in {OrderStatus.PARTIALLY_REFUNDED, OrderStatus.REFUNDED}:
        return order
    return _apply_transition(
        order=order,
        new_status=OrderStatus.PARTIALLY_REFUNDED,
        changed_by=changed_by,
        notes=reason or "Partial refund issued.",
    )


# ─────────────────────────────────────────────────────────────
#  Private helpers
# ─────────────────────────────────────────────────────────────

def _build_temp_cart_from_items(items: list[dict]) -> tuple[Cart, list[CartItem]]:
    if not items:
        raise ValidationError("At least one item is required.")

    merged: dict[str, int] = {}
    for row in items:
        variant_id = str(row.get("variant_id", "")).strip()
        quantity = int(row.get("quantity", 0) or 0)
        if not variant_id or quantity < 1:
            raise ValidationError("Each order item must include variant_id and quantity >= 1.")
        merged[variant_id] = merged.get(variant_id, 0) + quantity

    variant_ids = list(merged.keys())
    variants = {
        str(v.id): v
        for v in ProductVariant.objects.select_related("product__category").filter(
            id__in=variant_ids,
            is_active=True,
            product__is_active=True,
        )
    }
    missing = [vid for vid in variant_ids if vid not in variants]
    if missing:
        raise ValidationError(f"Some variants are invalid or inactive: {', '.join(missing)}")

    temp_cart = Cart.objects.create(
        user=None,
        session_key=f"admin-order-{uuid.uuid4()}",
        status="active",
    )
    created_items: list[CartItem] = []
    for vid, qty in merged.items():
        variant = variants[vid]
        created_items.append(
            CartItem.objects.create(
                cart=temp_cart,
                variant=variant,
                quantity=qty,
                unit_price=variant.effective_price,
                compare_at_price=variant.display_compare_at_price,
            )
        )

    return temp_cart, created_items


def _advance_admin_order_status(*, order: Order, target_status: str, changed_by=None) -> Order:
    """
    Optionally advance a newly placed admin order to a later state.
    """
    target = (target_status or OrderStatus.PLACED).lower()
    if target == OrderStatus.PLACED:
        return order
    if target == OrderStatus.CANCELLED:
        return cancel_order(order=order, changed_by=changed_by, reason="Cancelled during admin create flow.")
    if target == OrderStatus.PAID:
        return mark_paid(order=order, changed_by=changed_by)
    if target == OrderStatus.PROCESSING:
        mark_paid(order=order, changed_by=changed_by)
        return _apply_transition(order=order, new_status=OrderStatus.PROCESSING, changed_by=changed_by, notes="Processing from admin create flow.")
    if target == OrderStatus.SHIPPED:
        mark_paid(order=order, changed_by=changed_by)
        _apply_transition(
            order=order,
            new_status=OrderStatus.PROCESSING,
            changed_by=changed_by,
            notes="Processing from admin create flow.",
        )
        return mark_shipped(order=order, changed_by=changed_by)
    if target == OrderStatus.DELIVERED:
        mark_paid(order=order, changed_by=changed_by)
        _apply_transition(
            order=order,
            new_status=OrderStatus.PROCESSING,
            changed_by=changed_by,
            notes="Processing from admin create flow.",
        )
        mark_shipped(order=order, changed_by=changed_by)
        return mark_delivered(order=order, changed_by=changed_by)
    if target == OrderStatus.COMPLETED:
        mark_paid(order=order, changed_by=changed_by)
        _apply_transition(
            order=order,
            new_status=OrderStatus.PROCESSING,
            changed_by=changed_by,
            notes="Processing from admin create flow.",
        )
        mark_shipped(order=order, changed_by=changed_by)
        mark_delivered(order=order, changed_by=changed_by)
        return mark_completed(order=order, changed_by=changed_by, notes="Completed from admin create flow.")
    if target == OrderStatus.REFUNDED:
        mark_paid(order=order, changed_by=changed_by)
        _apply_transition(
            order=order,
            new_status=OrderStatus.PROCESSING,
            changed_by=changed_by,
            notes="Processing from admin create flow.",
        )
        mark_shipped(order=order, changed_by=changed_by)
        mark_delivered(order=order, changed_by=changed_by)
        mark_completed(order=order, changed_by=changed_by, notes="Completed before refund in admin create flow.")
        return mark_refunded(order=order, changed_by=changed_by, reason="Refunded from admin create flow.")
    raise ValidationError(f"Unsupported target status '{target_status}' for admin item-based order create.")

def _apply_transition(
    *,
    order: Order,
    new_status: str,
    changed_by=None,
    notes: str = "",
) -> Order:
    """
    Apply a status transition after validating it against STATE_TRANSITIONS.
    Writes an immutable OrderStatusHistory entry.
    """
    if new_status not in STATE_TRANSITIONS.get(order.status, set()):
        raise ConflictError(
            f"Invalid transition: '{order.status}' → '{new_status}' "
            f"for order '{order.order_number}'."
        )

    old_status = order.status

    # Update status + event-specific timestamp
    order.status = new_status
    update_fields = ["status", "updated_at"]

    if new_status == OrderStatus.PLACED:
        order.placed_at = timezone.now()
        update_fields.append("placed_at")
    elif new_status == OrderStatus.CANCELLED:
        order.cancelled_at = timezone.now()
        update_fields.append("cancelled_at")

    order.save(update_fields=update_fields)

    # Immutable history entry
    OrderStatusHistory.objects.create(
        order=order,
        from_status=old_status,
        to_status=new_status,
        changed_by=changed_by,
        notes=notes,
    )

    logger.info(
        "order_status_changed",
        order_id=str(order.id),
        order_number=order.order_number,
        from_status=old_status,
        to_status=new_status,
        user_id=str(changed_by.id) if changed_by else "system",
    )
    log_activity(
        user=changed_by,
        actor_type=(
            ActorType.ADMIN
            if getattr(changed_by, "role", "") == "admin"
            else ActorType.STAFF
            if getattr(changed_by, "role", "") == "staff"
            else ActorType.SYSTEM
        ),
        action=AuditAction.STATUS_CHANGE,
        entity_type="order",
        entity_id=str(order.id),
        description=f"Order {order.order_number} moved from {old_status} to {new_status}",
        metadata={
            "order_number": order.order_number,
            "from_status": old_status,
            "to_status": new_status,
            "notes": notes,
        },
    )
    return order
