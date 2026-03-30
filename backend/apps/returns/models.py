"""
returns.models
~~~~~~~~~~~~~~

State machines:
═══════════════

ReturnRequest:
  SUBMITTED → UNDER_REVIEW → APPROVED → ITEMS_RECEIVED → INSPECTED
                                                               │
                                              ┌────────────────┤
                                              ↓                ↓
                                     REFUND_INITIATED      REJECTED_AFTER_INSPECTION
                                              ↓
                                          COMPLETED
                  ↓ (at any point before ITEMS_RECEIVED)
               REJECTED

ExchangeRequest:
  SUBMITTED → UNDER_REVIEW → APPROVED → ITEMS_RECEIVED → INSPECTED
                                                               │
                                              ┌────────────────┤
                                              ↓                ↓
                                      EXCHANGE_SHIPPED    REJECTED_AFTER_INSPECTION
                                              ↓
                                          COMPLETED
                  ↓
               REJECTED

ReturnPolicy:
  One global policy (+ optional category-level overrides in JSON).
  Controls: return window, restocking fee, eligible order statuses,
            non-returnable category/product IDs.

ReturnItem / ExchangeItem:
  Line-level items referencing the original OrderItem.
  Each item carries: reason_code, condition_on_receipt (filled after items arrive).

Return number: RET-YYYY-NNNNN
Exchange number: EXC-YYYY-NNNNN
"""

import uuid
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator


# ─────────────────────────────────────────────────────────────
#  Reason codes
# ─────────────────────────────────────────────────────────────

class ReturnReason(models.TextChoices):
    DEFECTIVE          = "defective",          _("Product is defective / not working")
    DAMAGED_IN_TRANSIT = "damaged_transit",    _("Damaged during shipping")
    WRONG_ITEM         = "wrong_item",         _("Wrong item sent")
    NOT_AS_DESCRIBED   = "not_as_described",   _("Not as described / pictured")
    CHANGED_MIND       = "changed_mind",       _("Changed my mind")
    SIZE_ISSUE         = "size_issue",         _("Size / fit issue")
    QUALITY_ISSUE      = "quality_issue",      _("Quality not satisfactory")
    DUPLICATE_ORDER    = "duplicate_order",    _("Ordered by mistake / duplicate")
    LATE_DELIVERY      = "late_delivery",      _("Delivered too late")
    OTHER              = "other",              _("Other")


class ItemCondition(models.TextChoices):
    GOOD          = "good",          _("Good — returned as-is, resellable")
    MINOR_DAMAGE  = "minor_damage",  _("Minor damage — refurbish needed")
    DAMAGED       = "damaged",       _("Damaged — cannot be resold")
    UNUSABLE      = "unusable",      _("Unusable / destroyed")
    MISSING_PARTS = "missing_parts", _("Missing parts / accessories")


# ─────────────────────────────────────────────────────────────
#  Return status
# ─────────────────────────────────────────────────────────────

class ReturnStatus(models.TextChoices):
    SUBMITTED                  = "submitted",                _("Submitted")
    UNDER_REVIEW               = "under_review",             _("Under Review")
    APPROVED                   = "approved",                 _("Approved")
    REJECTED                   = "rejected",                 _("Rejected")
    ITEMS_RECEIVED             = "items_received",           _("Items Received")
    INSPECTED                  = "inspected",                _("Inspected")
    REJECTED_AFTER_INSPECTION  = "rejected_after_inspection", _("Rejected After Inspection")
    REFUND_INITIATED           = "refund_initiated",         _("Refund Initiated")
    COMPLETED                  = "completed",                _("Completed")


RETURN_TRANSITIONS: dict[str, set[str]] = {
    ReturnStatus.SUBMITTED:                 {ReturnStatus.UNDER_REVIEW, ReturnStatus.REJECTED},
    ReturnStatus.UNDER_REVIEW:              {ReturnStatus.APPROVED,     ReturnStatus.REJECTED},
    ReturnStatus.APPROVED:                  {ReturnStatus.ITEMS_RECEIVED},
    ReturnStatus.ITEMS_RECEIVED:            {ReturnStatus.INSPECTED},
    ReturnStatus.INSPECTED:                 {ReturnStatus.REFUND_INITIATED, ReturnStatus.REJECTED_AFTER_INSPECTION},
    ReturnStatus.REFUND_INITIATED:          {ReturnStatus.COMPLETED},
    ReturnStatus.REJECTED:                  set(),
    ReturnStatus.REJECTED_AFTER_INSPECTION: set(),
    ReturnStatus.COMPLETED:                 set(),
}

# Statuses that allow refund to be triggered
REFUND_READY_STATUSES = {ReturnStatus.INSPECTED, ReturnStatus.REFUND_INITIATED}


# ─────────────────────────────────────────────────────────────
#  Exchange status
# ─────────────────────────────────────────────────────────────

class ExchangeStatus(models.TextChoices):
    SUBMITTED                  = "submitted",                _("Submitted")
    UNDER_REVIEW               = "under_review",             _("Under Review")
    APPROVED                   = "approved",                 _("Approved")
    REJECTED                   = "rejected",                 _("Rejected")
    ITEMS_RECEIVED             = "items_received",           _("Items Received")
    INSPECTED                  = "inspected",                _("Inspected")
    REJECTED_AFTER_INSPECTION  = "rejected_after_inspection", _("Rejected After Inspection")
    EXCHANGE_SHIPPED           = "exchange_shipped",         _("Exchange Shipped")
    COMPLETED                  = "completed",                _("Completed")


EXCHANGE_TRANSITIONS: dict[str, set[str]] = {
    ExchangeStatus.SUBMITTED:                {ExchangeStatus.UNDER_REVIEW, ExchangeStatus.REJECTED},
    ExchangeStatus.UNDER_REVIEW:             {ExchangeStatus.APPROVED,     ExchangeStatus.REJECTED},
    ExchangeStatus.APPROVED:                 {ExchangeStatus.ITEMS_RECEIVED},
    ExchangeStatus.ITEMS_RECEIVED:           {ExchangeStatus.INSPECTED},
    ExchangeStatus.INSPECTED:               {ExchangeStatus.EXCHANGE_SHIPPED, ExchangeStatus.REJECTED_AFTER_INSPECTION},
    ExchangeStatus.EXCHANGE_SHIPPED:         {ExchangeStatus.COMPLETED},
    ExchangeStatus.REJECTED:                 set(),
    ExchangeStatus.REJECTED_AFTER_INSPECTION: set(),
    ExchangeStatus.COMPLETED:               set(),
}


# ─────────────────────────────────────────────────────────────
#  Return Policy  (singleton per site, plus per-category overrides)
# ─────────────────────────────────────────────────────────────

class ReturnPolicy(models.Model):
    """
    Single global return policy.
    Use get_active_policy() to retrieve — only one row should exist.

    category_overrides (JSON):
      [
        {
          "category_id": "uuid",
          "max_return_days": 3,
          "non_returnable": false
        }
      ]
    """
    name                    = models.CharField(max_length=200, default="Default Return Policy")
    is_active               = models.BooleanField(default=True, db_index=True)

    max_return_days         = models.PositiveSmallIntegerField(
        default=7,
        help_text="Number of days after delivery within which a return can be submitted.",
    )
    max_exchange_days       = models.PositiveSmallIntegerField(
        default=14,
        help_text="Number of days after delivery within which an exchange can be submitted.",
    )
    eligible_order_statuses = models.JSONField(
        default=list,
        help_text='Order statuses eligible for return, e.g. ["delivered","completed"]',
    )
    non_returnable_category_ids = models.JSONField(
        default=list,
        help_text="List of category UUIDs whose products cannot be returned.",
    )
    non_returnable_reason   = models.TextField(
        blank=True, default="This product is not eligible for return.",
    )
    restocking_fee_pct      = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Restocking fee as a % of order item price (deducted from refund).",
    )
    requires_original_packaging = models.BooleanField(default=False)
    category_overrides      = models.JSONField(
        default=list, blank=True,
        help_text="Per-category policy overrides.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = _("return policy")
        verbose_name_plural = _("return policies")

    def __str__(self):
        return f"{self.name} — {self.max_return_days}d return / {self.max_exchange_days}d exchange"


# ─────────────────────────────────────────────────────────────
#  Return Request
# ─────────────────────────────────────────────────────────────

class ReturnRequest(models.Model):
    id             = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    return_number  = models.CharField(max_length=30, unique=True, blank=True, db_index=True)

    order          = models.ForeignKey(
        "orders.Order", on_delete=models.PROTECT, related_name="return_requests"
    )
    user           = models.ForeignKey(
        "accounts.User", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="return_requests",
    )
    status         = models.CharField(
        max_length=30, choices=ReturnStatus.choices,
        default=ReturnStatus.SUBMITTED, db_index=True,
    )

    # Refund info
    refund_amount          = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    restocking_fee_applied = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_refund_ready        = models.BooleanField(default=False, db_index=True)
    refund_transaction     = models.ForeignKey(
        "payments.PaymentTransaction", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="return_refunds",
    )

    # Pickup / shipping
    pickup_address      = models.JSONField(default=dict, blank=True)
    return_tracking_no  = models.CharField(max_length=200, blank=True)
    return_carrier      = models.CharField(max_length=100, blank=True)

    notes               = models.TextField(blank=True, help_text="Customer notes.")
    staff_notes         = models.TextField(blank=True, help_text="Internal staff notes.")
    rejection_reason    = models.TextField(blank=True)

    # Timestamps
    approved_at         = models.DateTimeField(null=True, blank=True)
    items_received_at   = models.DateTimeField(null=True, blank=True)
    inspected_at        = models.DateTimeField(null=True, blank=True)
    refund_initiated_at = models.DateTimeField(null=True, blank=True)
    completed_at        = models.DateTimeField(null=True, blank=True)
    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = _("return request")
        verbose_name_plural = _("return requests")
        ordering            = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.return_number:
            year  = timezone.now().year
            count = ReturnRequest.objects.filter(created_at__year=year).count() + 1
            self.return_number = f"RET-{year}-{count:05d}"
        super().save(*args, **kwargs)

    def can_transition_to(self, status: str) -> bool:
        return status in RETURN_TRANSITIONS.get(self.status, set())

    def __str__(self):
        return f"{self.return_number} [{self.status}]"


class ReturnItem(models.Model):
    """One line in a ReturnRequest, tied to an original OrderItem."""

    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    return_request  = models.ForeignKey(ReturnRequest, on_delete=models.CASCADE, related_name="items")
    order_item      = models.ForeignKey(
        "orders.OrderItem", on_delete=models.PROTECT, related_name="return_items"
    )
    variant         = models.ForeignKey(
        "catalog.ProductVariant", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="return_items",
    )
    warehouse       = models.ForeignKey(
        "inventory.Warehouse", null=True, blank=True,
        on_delete=models.SET_NULL, help_text="Warehouse to reintegrate stock into.",
    )

    quantity        = models.PositiveIntegerField()
    reason_code     = models.CharField(max_length=30, choices=ReturnReason.choices)
    reason_detail   = models.TextField(blank=True)
    condition       = models.CharField(
        max_length=20, choices=ItemCondition.choices, blank=True,
        help_text="Filled in by staff when items are received.",
    )

    # Price snapshot for refund calculation
    unit_price      = models.DecimalField(max_digits=12, decimal_places=2)
    refund_amount   = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Stock reintegrated?
    stock_reintegrated = models.BooleanField(default=False)

    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = _("return item")
        verbose_name_plural = _("return items")

    def __str__(self):
        return f"{self.order_item.sku} × {self.quantity} → {self.return_request.return_number}"


# ─────────────────────────────────────────────────────────────
#  Exchange Request
# ─────────────────────────────────────────────────────────────

class ExchangeRequest(models.Model):
    id               = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    exchange_number  = models.CharField(max_length=30, unique=True, blank=True, db_index=True)

    order            = models.ForeignKey(
        "orders.Order", on_delete=models.PROTECT, related_name="exchange_requests"
    )
    user             = models.ForeignKey(
        "accounts.User", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="exchange_requests",
    )
    status           = models.CharField(
        max_length=30, choices=ExchangeStatus.choices,
        default=ExchangeStatus.SUBMITTED, db_index=True,
    )

    # Shipping for returned items
    return_tracking_no   = models.CharField(max_length=200, blank=True)
    return_carrier       = models.CharField(max_length=100, blank=True)
    # Shipping for replacement items
    exchange_tracking_no = models.CharField(max_length=200, blank=True)
    exchange_carrier     = models.CharField(max_length=100, blank=True)
    shipping_address     = models.JSONField(default=dict, blank=True)

    notes            = models.TextField(blank=True)
    staff_notes      = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)

    approved_at          = models.DateTimeField(null=True, blank=True)
    items_received_at    = models.DateTimeField(null=True, blank=True)
    inspected_at         = models.DateTimeField(null=True, blank=True)
    exchange_shipped_at  = models.DateTimeField(null=True, blank=True)
    completed_at         = models.DateTimeField(null=True, blank=True)
    created_at           = models.DateTimeField(auto_now_add=True)
    updated_at           = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = _("exchange request")
        verbose_name_plural = _("exchange requests")
        ordering            = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.exchange_number:
            year  = timezone.now().year
            count = ExchangeRequest.objects.filter(created_at__year=year).count() + 1
            self.exchange_number = f"EXC-{year}-{count:05d}"
        super().save(*args, **kwargs)

    def can_transition_to(self, status: str) -> bool:
        return status in EXCHANGE_TRANSITIONS.get(self.status, set())

    def __str__(self):
        return f"{self.exchange_number} [{self.status}]"


class ExchangeItem(models.Model):
    """One line in an ExchangeRequest: original item → replacement variant."""

    id                = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    exchange_request  = models.ForeignKey(ExchangeRequest, on_delete=models.CASCADE, related_name="items")
    order_item        = models.ForeignKey(
        "orders.OrderItem", on_delete=models.PROTECT, related_name="exchange_items"
    )

    # Returned variant
    original_variant  = models.ForeignKey(
        "catalog.ProductVariant", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="exchange_returns",
    )
    # Replacement variant (may differ by size/colour)
    replacement_variant = models.ForeignKey(
        "catalog.ProductVariant", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="exchange_replacements",
    )
    warehouse         = models.ForeignKey(
        "inventory.Warehouse", null=True, blank=True, on_delete=models.SET_NULL,
    )

    quantity          = models.PositiveIntegerField()
    reason_code       = models.CharField(max_length=30, choices=ReturnReason.choices)
    reason_detail     = models.TextField(blank=True)
    condition         = models.CharField(max_length=20, choices=ItemCondition.choices, blank=True)

    price_difference  = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Positive = customer owes; Negative = we owe customer.",
    )
    stock_reintegrated = models.BooleanField(default=False)

    created_at        = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = _("exchange item")
        verbose_name_plural = _("exchange items")

    def __str__(self):
        orig = self.original_variant.sku if self.original_variant else "?"
        repl = self.replacement_variant.sku if self.replacement_variant else "?"
        return f"{orig} → {repl} × {self.quantity}"


# ─────────────────────────────────────────────────────────────
#  Return / Exchange Status History  (immutable)
# ─────────────────────────────────────────────────────────────

class ReturnStatusHistory(models.Model):
    """Immutable log for both ReturnRequest and ExchangeRequest transitions."""

    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # One of these will be set (not both)
    return_request  = models.ForeignKey(
        ReturnRequest, null=True, blank=True,
        on_delete=models.CASCADE, related_name="status_history",
    )
    exchange_request = models.ForeignKey(
        ExchangeRequest, null=True, blank=True,
        on_delete=models.CASCADE, related_name="status_history",
    )
    from_status     = models.CharField(max_length=30, blank=True)
    to_status       = models.CharField(max_length=30)
    changed_by      = models.ForeignKey(
        "accounts.User", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="return_transitions",
    )
    notes           = models.TextField(blank=True)
    created_at      = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        ref = (
            self.return_request.return_number if self.return_request
            else self.exchange_request.exchange_number if self.exchange_request
            else "?"
        )
        return f"{ref}: {self.from_status or '—'} → {self.to_status}"
