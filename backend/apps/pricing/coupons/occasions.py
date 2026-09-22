"""
Birthday and anniversary gift coupons.

One customer, one occasion, one calendar year, one coupon. The uniqueness is
enforced by a database constraint rather than by this module remembering what
it did, because the thing most likely to issue a second coupon is a retry — a
worker that died after creating the coupon but before the email went out, and
a beat that fires again after a restart.

Nothing here decides *when* a gift is due; that is the sweep in
``apps/pricing/tasks.py``. This module only mints the coupon.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from core.logging import get_logger

from .models import Coupon, CouponOccasion, CouponType

logger = get_logger(__name__)

CODE_PREFIXES = {
    CouponOccasion.BIRTHDAY: "BDAY",
    CouponOccasion.ANNIVERSARY: "ANNIV",
}


@dataclass(frozen=True)
class GiftTerms:
    """The shape of the gift, read from settings so it can change without a deploy."""

    percent: int
    max_discount: int
    min_order_value: int
    valid_days: int
    lead_days: int


def gift_terms() -> GiftTerms:
    return GiftTerms(
        percent=int(getattr(settings, "OCCASION_GIFT_PERCENT", 15)),
        max_discount=int(getattr(settings, "OCCASION_GIFT_MAX_DISCOUNT", 500)),
        min_order_value=int(getattr(settings, "OCCASION_GIFT_MIN_ORDER_VALUE", 0)),
        valid_days=int(getattr(settings, "OCCASION_GIFT_VALID_DAYS", 14)),
        lead_days=int(getattr(settings, "OCCASION_GIFT_LEAD_DAYS", 3)),
    )


def _generate_code(occasion: str) -> str:
    """
    A code that is awkward to guess.

    ``BDAY-7F2A9C31``. Not sequential and not derived from the customer id: a
    guessable personal code would let someone else redeem a gift even though
    the ownership check would then reject them — a nuisance rather than a
    breach, but an avoidable one.
    """
    prefix = CODE_PREFIXES.get(occasion, "GIFT")
    return f"{prefix}-{secrets.token_hex(4).upper()}"


def _window(*, occasion_date: date, terms: GiftTerms) -> tuple[datetime, datetime]:
    """
    Valid from the moment it is issued until ``valid_days`` after the occasion.

    Starting at issue rather than on the day itself is deliberate: the email
    arrives a few days early so the customer can actually order something and
    have it arrive, and a coupon they cannot use yet reads as a broken email.
    """
    current_tz = timezone.get_current_timezone()
    start = timezone.now()
    end = datetime.combine(occasion_date + timedelta(days=terms.valid_days), time.max)
    end = timezone.make_aware(end, current_tz)
    return start, end


@transaction.atomic
def issue_occasion_coupon(*, user, occasion: str, occasion_date: date) -> tuple[Coupon | None, bool]:
    """
    Mint this year's gift coupon for one customer.

    Returns ``(coupon, created)``. ``created=False`` means one already existed
    for this customer / occasion / year — the normal outcome of a retry, and
    not an error. ``(None, False)`` means we declined to issue one.
    """
    terms = gift_terms()
    year = occasion_date.year

    existing = Coupon.objects.filter(
        assigned_user=user, occasion=occasion, occasion_year=year
    ).first()
    if existing is not None:
        return existing, False

    start, end = _window(occasion_date=occasion_date, terms=terms)

    # A code collision is vanishingly unlikely (2^32 per prefix) but `code` is
    # unique, so a collision would surface as an IntegrityError on a customer's
    # birthday. Cheap to retry, expensive to debug later.
    for _attempt in range(5):
        code = _generate_code(occasion)
        if Coupon.objects.filter(code=code).exists():
            continue
        try:
            with transaction.atomic():
                coupon = Coupon.objects.create(
                    code=code,
                    type=CouponType.PERCENTAGE,
                    value=terms.percent,
                    max_discount=terms.max_discount or None,
                    min_order_value=terms.min_order_value,
                    # Both limits are 1. usage_limit alone would be enough given
                    # the ownership check, but per_user_limit is what the older
                    # validation path reads, and defence in depth on a discount
                    # costs nothing.
                    usage_limit=1,
                    per_user_limit=1,
                    start_date=start,
                    end_date=end,
                    is_active=True,
                    assigned_user=user,
                    occasion=occasion,
                    occasion_year=year,
                )
        except IntegrityError:
            # Either the code collided after the existence check (a race with a
            # parallel worker), or the per-user/occasion/year constraint fired
            # because another worker got there first. The second case is the
            # one that matters and it is a success, not a failure.
            duplicate = Coupon.objects.filter(
                assigned_user=user, occasion=occasion, occasion_year=year
            ).first()
            if duplicate is not None:
                return duplicate, False
            continue

        logger.info(
            "occasion_coupon_issued",
            user_id=str(user.id), occasion=occasion, year=year, code=coupon.code,
        )
        return coupon, True

    logger.error(
        "occasion_coupon_code_exhausted",
        user_id=str(user.id), occasion=occasion, year=year,
    )
    return None, False
