from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone

from core.exceptions import NotFoundError, ValidationError
from apps.cart.selectors import calculate_cart_totals

from .models import Coupon, CouponType, CouponUsage


class CouponService:
    @staticmethod
    def get_coupon(code: str) -> Coupon:
        if not code:
            raise ValidationError("Coupon code is required.")
        try:
            return Coupon.objects.get(code__iexact=code.strip())
        except Coupon.DoesNotExist:
            raise NotFoundError("Coupon not found.")

    @staticmethod
    def validate_coupon(*, coupon: Coupon, user, cart) -> None:
        now = timezone.now()
        if not coupon.is_active:
            raise ValidationError("Coupon is inactive.")
        if coupon.start_date > now:
            raise ValidationError("Coupon is not active yet.")
        if coupon.end_date < now:
            raise ValidationError("Coupon has expired.")

        totals = calculate_cart_totals(cart)
        subtotal = totals["subtotal"]
        if subtotal < coupon.min_order_value:
            raise ValidationError(
                f"Minimum order value for this coupon is {coupon.min_order_value}."
            )

        if coupon.usage_limit is not None:
            total_used = CouponUsage.objects.filter(coupon=coupon).count()
            if total_used >= coupon.usage_limit:
                raise ValidationError("Coupon usage limit reached.")

        if user and coupon.per_user_limit is not None:
            user_used = CouponUsage.objects.filter(coupon=coupon, user=user).count()
            if user_used >= coupon.per_user_limit:
                raise ValidationError("Per-user coupon usage limit reached.")

    @staticmethod
    def calculate_discount(*, coupon: Coupon, cart) -> Decimal:
        subtotal = calculate_cart_totals(cart)["subtotal"]
        if subtotal <= 0:
            return Decimal("0")

        if coupon.type == CouponType.PERCENTAGE:
            discount = (subtotal * coupon.value / Decimal("100")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        else:
            discount = coupon.value

        if coupon.max_discount is not None:
            discount = min(discount, coupon.max_discount)
        discount = min(discount, subtotal)
        return max(Decimal("0"), discount)

    @staticmethod
    def apply_coupon(*, cart, code: str, user=None) -> dict:
        coupon = CouponService.get_coupon(code)
        CouponService.validate_coupon(coupon=coupon, user=user, cart=cart)
        amount = CouponService.calculate_discount(coupon=coupon, cart=cart)
        return {
            "code": coupon.code,
            "amount": amount,
            "type": coupon.type,
        }

    @staticmethod
    def record_usage(*, coupon_code: str, user, cart, order, discount_amount: Decimal) -> None:
        coupon = CouponService.get_coupon(coupon_code)
        CouponUsage.objects.create(
            coupon=coupon,
            user=user if user and user.is_authenticated else None,
            cart=cart,
            order=order,
            discount_amount=discount_amount,
        )
