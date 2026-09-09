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
    # Cash at the counter. Distinct from COD, which is cash collected by a
    # courier on a shipped order — different reconciliation, different owner.
    CASH         = "cash",         _("Cash at counter")
    CASHFREE     = "cashfree",     _("Cashfree")
    RAZORPAY     = "razorpay",     _("Razorpay")
    PHONEPE      = "phonepe",      _("PhonePe")
    STRIPE       = "stripe",       _("Stripe")
    UPI          = "upi",          _("UPI")
    BANK_TRANSFER = "bank_transfer", _("Bank Transfer")


class PaymentStatus(models.TextChoices):
    PENDING   = "pending",   _("Pending")
    # Real money has been collected, but not all of it. A counter sale where the
    # customer paid part in cash and then walked away from the UPI leg lives here.
    # It is a genuine state with cash against it, not a transient UI condition.
    PARTIALLY_PAID = "partially_paid", _("Partially Paid")
    PAID      = "paid",      _("Paid")
    FAILED    = "failed",    _("Failed")
    REFUNDED  = "refunded",  _("Refunded")
    PARTIALLY_REFUNDED = "partially_refunded", _("Partially Refunded")


class SalesChannel(models.TextChoices):
    """Where the order was taken. Every existing report gets an online/POS split."""
    ONLINE = "online", _("Online")
    POS    = "pos",    _("Point of sale")


class FulfilmentType(models.TextChoices):
    """
    Load-bearing: shipping tasks must never try to book a courier shipment for a
    customer who walked away from the stall with the earrings in their hand.
    """
    SHIP       = "ship",       _("Ship to customer")
    CARRY_AWAY = "carry_away", _("Carried away from counter")


class ShippingApprovalStatus(models.TextChoices):
    PENDING_SHIPPING_APPROVAL = "pending_shipping_approval", _("Pending Shipping Approval")
    APPROVED = "approved", _("Approved")
    REJECTED = "rejected", _("Rejected")
    # A counter sale has no shipment to approve — the customer is holding the
    # parcel. It used to be marked REJECTED to keep it out of the approval
    # queue, which worked but read as though someone had refused to ship it.
    # "Rejected" is a decision; this is the absence of a question.
    NOT_REQUIRED = "not_required", _("Not required — handed over")


class FulfillmentMethod(models.TextChoices):
    UNASSIGNED = "unassigned", _("Unassigned")
    COUNTER = "counter", _("Handed over at the counter")
    LOCAL_DELIVERY = "local_delivery", _("Local Delivery")
    NIMBUSPOST = "nimbuspost", _("NimbusPost")
    SHIPROCKET = "shiprocket", _("Shiprocket")


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

    # ── Point of sale ────────────────────────────────────────
    channel = models.CharField(
        max_length=20, choices=SalesChannel.choices,
        default=SalesChannel.ONLINE, db_index=True,
    )
    fulfilment_type = models.CharField(
        max_length=20, choices=FulfilmentType.choices,
        default=FulfilmentType.SHIP, db_index=True,
    )
    pos_terminal = models.ForeignKey(
        "pos.POSTerminal",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="orders",
    )
    pos_shift = models.ForeignKey(
        "pos.POSShift",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="orders",
        help_text="The trading session this sale belongs to.",
    )
    created_by_staff = models.ForeignKey(
        "accounts.User",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="pos_orders_created",
        help_text="Staff member who rang up this sale. Null for online orders.",
    )
    contact_name = models.CharField(
        max_length=150, blank=True,
        help_text="Walk-in customer name. Kept on the order even when no account exists.",
    )
    contact_phone = models.CharField(
        max_length=20, blank=True, db_index=True,
        help_text="Phone is the identity at the counter — this is what customer "
                  "lookup matches on.",
    )
    contact_wants_account = models.BooleanField(
        default=True,
        help_text="Did the customer agree to an account being created? Kept apart "
                  "from the email itself: the email is needed for the receipt "
                  "whatever they decided, and a receipt is transactional. An "
                  "existing account is still linked either way — declining means "
                  "no NEW account, not no record.",
    )

    # ── Manual discount audit ────────────────────────────────
    # A staff override is the margin leak a POS has to be able to explain later,
    # so who / how much / why are stored, not just the resulting total.
    manual_discount_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
    )
    manual_discount_reason = models.CharField(max_length=100, blank=True)
    manual_discount_approved_by = models.ForeignKey(
        "accounts.User",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_pos_discounts",
        help_text="Set when the discount exceeded the staff ceiling and a manager "
                  "authorised it.",
    )
    shipping_approval_status = models.CharField(
        max_length=40,
        choices=ShippingApprovalStatus.choices,
        default=ShippingApprovalStatus.PENDING_SHIPPING_APPROVAL,
        db_index=True,
    )
    fulfillment_method = models.CharField(
        max_length=30,
        choices=FulfillmentMethod.choices,
        default=FulfillmentMethod.UNASSIGNED,
        db_index=True,
    )
    shipping_approved_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="shipping_approved_orders",
    )
    shipping_approved_at = models.DateTimeField(null=True, blank=True)
    shipping_approval_notes = models.TextField(blank=True)

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
            models.Index(fields=["shipping_approval_status", "fulfillment_method"]),
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
        allowed = set(STATE_TRANSITIONS.get(self.status, set()))

        # A carried-away sale is finished the moment it is paid: the goods
        # changed hands across the counter. The shared map routes every order
        # through PROCESSING → SHIPPED → DELIVERED before COMPLETED, so without
        # this a counter sale would sit at PAID for ever, permanently open in
        # every report. Narrow on purpose — carry-away only, from PAID only —
        # so nothing lets an online order skip its shipment.
        if (
            self.status == OrderStatus.PAID
            and self.fulfilment_type == FulfilmentType.CARRY_AWAY
        ):
            allowed.add(OrderStatus.COMPLETED)

        return new_status in allowed

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
