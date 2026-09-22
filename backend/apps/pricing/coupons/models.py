from __future__ import annotations

import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _


class CouponType(models.TextChoices):
    PERCENTAGE = "percentage", _("Percentage")
    FIXED = "fixed", _("Fixed")


class CouponOccasion(models.TextChoices):
    """
    Why a personal coupon exists. Blank for ordinary campaign coupons, which is
    every coupon that existed before this field did.
    """
    BIRTHDAY = "birthday", _("Birthday")
    ANNIVERSARY = "anniversary", _("Anniversary")


class Coupon(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=50, unique=True, db_index=True)
    type = models.CharField(max_length=20, choices=CouponType.choices)
    value = models.DecimalField(max_digits=12, decimal_places=2)
    max_discount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    min_order_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    usage_limit = models.PositiveIntegerField(null=True, blank=True)
    per_user_limit = models.PositiveIntegerField(null=True, blank=True)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True, db_index=True)

    # ── Personal coupons ───────────────────────────────────────
    # A coupon with an assigned_user belongs to that customer and nobody else.
    # CouponService.validate_coupon enforces it: without that check a birthday
    # code shared in a WhatsApp group is a public discount, which is exactly
    # how a gift programme turns into an unplanned sale.
    assigned_user = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="personal_coupons",
        help_text="If set, only this customer may redeem the coupon.",
    )
    occasion = models.CharField(
        max_length=20,
        choices=CouponOccasion.choices,
        blank=True,
        default="",
        help_text="Why this personal coupon was issued. Blank for campaign coupons.",
    )
    # The calendar year the occasion falls in. Together with (assigned_user,
    # occasion) this is what makes the daily sweep idempotent — a task that
    # runs twice, or a beat that fires after a restart, cannot issue two
    # birthday coupons for the same birthday.
    occasion_year = models.PositiveIntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["assigned_user", "occasion", "occasion_year"],
                condition=models.Q(assigned_user__isnull=False),
                name="pricing_unique_occasion_coupon_per_user_year",
            ),
        ]

    def __str__(self) -> str:
        return self.code

    @property
    def is_personal(self) -> bool:
        return self.assigned_user_id is not None


class CouponUsage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name="usages")
    user = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="coupon_usages",
    )
    cart = models.ForeignKey(
        "cart.Cart",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="coupon_usages",
    )
    order = models.ForeignKey(
        "orders.Order",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="coupon_usages",
    )
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    used_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-used_at"]
