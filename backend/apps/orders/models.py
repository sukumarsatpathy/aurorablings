"""
orders.models
~~~~~~~~~~~~~

State machine:
                               ┌──────────────────────────────────────────┐
                               │                                          │
  DRAFT ──► PLACED ──► PAID ──► PROCESSING ──► SHIPPED ──► DELIVERED ──► COMPLETED
    │           │         │
    └───────────┴─────────┴──► CANCELLED
                                    │
                              REFUNDED (from DELIVERED / COMPLETED)

Snapshots:
  - address_snapshot (JSON)  : full address at order placement time
  - unit_price / line_total   : price at cart-add time (CartItem snapshot)
  - product_name / sku / etc. : variant snapshot so historical orders are stable

Order number:
  UUID format (e.g. 2f96a0bb-0a7f-4e8b-9021-7aa54d9f1f2d)
  Generated in Order.save().
"""

import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator


# ─────────────────────────────────────────────────────────────
#  Order Status  (state machine)
# ─────────────────────────────────────────────────────────────

class OrderStatus(models.TextChoices):
    DRAFT       = "draft",       _("Draft")
    PLACED      = "placed",      _("Placed")
    PAID        = "paid",        _("Paid")
    PROCESSING  = "processing",  _("Processing")
    SHIPPED     = "shipped",     _("Shipped")
    DELIVERED   = "delivered",   _("Delivered")
    COMPLETED   = "completed",   _("Completed")
    PARTIALLY_REFUNDED = "partially_refunded", _("Partially Refunded")
    CANCELLED   = "cancelled",   _("Cancelled")
    REFUNDED    = "refunded",    _("Refunded")


# Valid forward transitions
STATE_TRANSITIONS: dict[str, set[str]] = {
    OrderStatus.DRAFT:      {OrderStatus.PLACED,     OrderStatus.CANCELLED},
    OrderStatus.PLACED:     {OrderStatus.PAID,       OrderStatus.CANCELLED, OrderStatus.PARTIALLY_REFUNDED, OrderStatus.REFUNDED},
    OrderStatus.PAID:       {OrderStatus.PROCESSING, OrderStatus.CANCELLED, OrderStatus.PARTIALLY_REFUNDED, OrderStatus.REFUNDED},
    OrderStatus.PROCESSING: {OrderStatus.SHIPPED,    OrderStatus.CANCELLED, OrderStatus.PARTIALLY_REFUNDED, OrderStatus.REFUNDED},
    OrderStatus.SHIPPED:    {OrderStatus.DELIVERED,  OrderStatus.PARTIALLY_REFUNDED, OrderStatus.REFUNDED},
    OrderStatus.DELIVERED:  {OrderStatus.COMPLETED,  OrderStatus.PARTIALLY_REFUNDED, OrderStatus.REFUNDED},
    OrderStatus.COMPLETED:  {OrderStatus.PARTIALLY_REFUNDED, OrderStatus.REFUNDED},
    OrderStatus.PARTIALLY_REFUNDED: {OrderStatus.REFUNDED},
    OrderStatus.CANCELLED:  set(),
    OrderStatus.REFUNDED:   set(),
}

# Statuses that allow stock reservation release
CANCELLABLE_STATUSES = {OrderStatus.DRAFT, OrderStatus.PLACED, OrderStatus.PAID, OrderStatus.PROCESSING}


# ─────────────────────────────────────────────────────────────
#  Payment Method
# ─────────────────────────────────────────────────────────────

class PaymentMethod(models.TextChoices):
    COD          = "cod",          _("Cash on Delivery")
    CASHFREE     = "cashfree",     _("Cashfree")
    RAZORPAY     = "razorpay",     _("Razorpay")
    STRIPE       = "stripe",       _("Stripe")
    UPI          = "upi",          _("UPI")
    BANK_TRANSFER = "bank_transfer", _("Bank Transfer")


class PaymentStatus(models.TextChoices):
    PENDING   = "pending",   _("Pending")
    PAID      = "paid",      _("Paid")
    FAILED    = "failed",    _("Failed")
    REFUNDED  = "refunded",  _("Refunded")
    PARTIALLY_REFUNDED = "partially_refunded", _("Partially Refunded")


# ─────────────────────────────────────────────────────────────
#  Order
# ─────────────────────────────────────────────────────────────

class Order(models.Model):
    """
    The central order entity.

    All financial totals are immutable snapshots — they reflect
    what the customer was charged, not current catalogue prices.
    """

    id            = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number  = models.CharField(max_length=64, unique=True, db_index=True, blank=True)

    # ── Ownership ─────────────────────────────────────────────
    user          = models.ForeignKey(
        "accounts.User",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="orders",
        help_text="Null for guest orders.",
    )
    guest_email   = models.EmailField(blank=True, help_text="For guest checkouts.")

    # ── Status ────────────────────────────────────────────────
    status          = models.CharField(
        max_length=25, choices=OrderStatus.choices,
        default=OrderStatus.DRAFT, db_index=True,
    )
    payment_status  = models.CharField(
        max_length=25, choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING, db_index=True,
    )
    payment_method  = models.CharField(
        max_length=20, choices=PaymentMethod.choices,
        blank=True,
    )
    payment_reference = models.CharField(
        max_length=200, blank=True,
        help_text="Gateway transaction ID / UPI ref.",
    )

    # ── Address snapshots (JSON — immutable after placement) ──
    shipping_address = models.JSONField(
        default=dict,
        help_text="Full address snapshot at order placement time.",
    )
    billing_address  = models.JSONField(
        default=dict, blank=True,
        help_text="Defaults to shipping_address if not provided.",
    )

    # ── Financials (all immutable after PLACED) ───────────────
    subtotal        = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    coupon_code     = models.CharField(max_length=50, blank=True, default="")
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    shipping_cost   = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_amount      = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    grand_total     = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency        = models.CharField(max_length=3, default="INR")

    # ── Fulfilment ────────────────────────────────────────────
    tracking_number  = models.CharField(max_length=200, blank=True)
    shipping_carrier = models.CharField(max_length=100, blank=True)
    notes            = models.TextField(blank=True, help_text="Customer-facing notes.")
    internal_notes   = models.TextField(blank=True, help_text="Staff-only notes.")

    # ── Warehouse used for this order ─────────────────────────
    warehouse        = models.ForeignKey(
        "inventory.Warehouse",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="orders",
    )

    # ── Source cart (nullable — cleared after conversion) ─────
    cart_id_snapshot = models.UUIDField(
        null=True, blank=True,
        help_text="ID of the cart this order was created from.",
    )

    # ── Timestamps ────────────────────────────────────────────
    placed_at    = models.DateTimeField(null=True, blank=True)
    paid_at      = models.DateTimeField(null=True, blank=True)
    shipped_at   = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = _("order")
        verbose_name_plural = _("orders")
        ordering            = ["-created_at"]
        indexes             = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["status", "created_at"]),
        ]

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = self._generate_order_number()
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_order_number() -> str:
        while True:
            candidate = str(uuid.uuid4())
            if not Order.objects.filter(order_number=candidate).exists():
                return candidate

    def can_transition_to(self, new_status: str) -> bool:
        return new_status in STATE_TRANSITIONS.get(self.status, set())

    @property
    def is_cancellable(self) -> bool:
        return self.status in CANCELLABLE_STATUSES

    @property
    def item_count(self) -> int:
        return self.items.aggregate(total=models.Sum("quantity"))["total"] or 0

    def __str__(self):
        return f"Order {self.order_number} [{self.status}]"


# ─────────────────────────────────────────────────────────────
#  Order Item  (price + product snapshot)
# ─────────────────────────────────────────────────────────────

class OrderItem(models.Model):
    """
    A line in the order.

    All fields are SNAPSHOTS — they never change after the order is placed.
    This ensures historical orders are always accurate even if products
    are updated or deleted later.
    """

    id      = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order   = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")

    # ── Variant reference (soft — nullable if variant deleted) ─
    variant = models.ForeignKey(
        "catalog.ProductVariant",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="order_items",
    )

    # ── Product snapshot (stable even after catalogue changes) ─
    sku              = models.CharField(max_length=100)
    product_name     = models.CharField(max_length=255)
    variant_name     = models.CharField(max_length=255, blank=True)
    product_snapshot = models.JSONField(
        default=dict,
        help_text="Full variant/product data at order time.",
    )

    # ── Pricing snapshot ──────────────────────────────────────
    quantity          = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price        = models.DecimalField(max_digits=12, decimal_places=2)
    compare_at_price  = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    line_total        = models.DecimalField(max_digits=12, decimal_places=2)

    # ── Warehouse stock was fulfilled from ────────────────────
    warehouse = models.ForeignKey(
        "inventory.Warehouse",
        null=True, blank=True,
        on_delete=models.SET_NULL,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = _("order item")
        verbose_name_plural = _("order items")
        ordering            = ["created_at"]

    def __str__(self):
        return f"{self.sku} × {self.quantity} — {self.order.order_number}"


# ─────────────────────────────────────────────────────────────
#  Order Status History  (immutable log)
# ─────────────────────────────────────────────────────────────

class OrderStatusHistory(models.Model):
    """
    Append-only log of every status transition.
    Rows are NEVER updated or deleted.
    """

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order        = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="status_history")
    from_status  = models.CharField(max_length=25, choices=OrderStatus.choices, blank=True)
    to_status    = models.CharField(max_length=25, choices=OrderStatus.choices)
    changed_by   = models.ForeignKey(
        "accounts.User",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="order_transitions",
    )
    notes        = models.TextField(blank=True)
    created_at   = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name        = _("order status history")
        verbose_name_plural = _("order status history")
        ordering            = ["created_at"]

    def __str__(self):
        return (
            f"{self.order.order_number}: "
            f"{self.from_status or '—'} → {self.to_status}"
        )
