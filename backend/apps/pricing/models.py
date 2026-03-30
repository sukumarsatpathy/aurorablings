"""
pricing.models
~~~~~~~~~~~~~~
Model entry-point for pricing module.
Keeps coupon models under apps/pricing/coupons/ while making Django discover them.
"""

from .coupons.models import Coupon, CouponUsage  # noqa: F401
