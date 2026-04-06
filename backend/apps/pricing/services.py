from __future__ import annotations

from decimal import Decimal

from apps.cart.selectors import calculate_cart_totals
from .coupons.services import CouponService


class PricingService:
    """
    Additive pricing layer that extends existing cart totals with coupon support.
    It does not replace existing cart/item pricing logic.
    """

    @staticmethod
    def calculate(*, cart, coupon_code: str | None = None, user=None, request=None) -> dict:
        totals = calculate_cart_totals(cart, request=request)
        subtotal = totals["subtotal"]

        coupon_data = None
        discount = Decimal("0")
        if coupon_code:
            coupon_data = CouponService.apply_coupon(cart=cart, code=coupon_code, user=user)
            discount = coupon_data["amount"]

        total = max(Decimal("0"), subtotal - discount)
        return {
            "subtotal": subtotal,
            "discount": discount,
            "total": total,
            "coupon": coupon_data,
            "cart_totals": totals,
        }
