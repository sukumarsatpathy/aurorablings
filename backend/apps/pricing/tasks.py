"""
The daily occasion sweep.

Runs once a morning, finds whose birthday or anniversary is ``lead_days`` away,
issues each of them a personal coupon and sends the email.

Design notes worth keeping:

* **The sweep is idempotent.** Re-running it issues nothing new — the coupon's
  unique constraint on (assigned_user, occasion, year) is the guard. That is
  what makes it safe to retry, safe to run by hand, and safe when beat fires
  twice after a restart.
* **A coupon is created before the email is sent, and the email failing does
  not roll it back.** The coupon is the gift; the email is only how we mention
  it. A customer whose email bounces still finds the coupon in their account.
* **29 February birthdays are handled.** In a non-leap year they are swept with
  1 March, otherwise those customers silently never get a birthday email and
  nobody finds out for four years.
* **Only customers with a usable email are swept**, since the whole point is to
  tell them. A counter customer with no email keeps the date on file and is
  picked up automatically the year after they give us one.
"""
from __future__ import annotations

import calendar
from datetime import date, timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from core.logging import get_logger

logger = get_logger(__name__)

# (occasion, model field on accounts.User)
OCCASION_FIELDS = (
    ("birthday", "date_of_birth"),
    ("anniversary", "anniversary_date"),
)


def _target_date(lead_days: int) -> date:
    return timezone.localdate() + timedelta(days=lead_days)


def _matches_for(*, field: str, target: date):
    """
    Everyone whose ``field`` falls on ``target``'s month and day.

    Year is ignored — that is the whole idea of an anniversary. The leap-day
    clause folds 29 February into 1 March in years that have no 29 February.
    """
    from apps.accounts.models import User, UserRole
    from django.db.models import Q

    match = Q(**{f"{field}__month": target.month, f"{field}__day": target.day})

    if target.month == 3 and target.day == 1 and not calendar.isleap(target.year):
        match |= Q(**{f"{field}__month": 2, f"{field}__day": 29})

    return (
        User.objects.filter(match)
        .filter(role=UserRole.CUSTOMER, is_active=True)
        .exclude(email="")
        .only("id", "email", "first_name", "last_name", field)
    )


@shared_task(bind=True, name="pricing.issue_occasion_coupons", max_retries=2)
def issue_occasion_coupons(self, *, lead_days: int | None = None, dry_run: bool = False) -> dict:
    """
    Issue birthday / anniversary coupons for everyone due in ``lead_days``.

    ``dry_run=True`` reports what it would do and writes nothing — run it that
    way the first time, against real data, before letting beat near it.
    """
    from apps.notifications.events import NotificationEvent
    from apps.pricing.coupons.occasions import gift_terms, issue_occasion_coupon

    if not getattr(settings, "OCCASION_GIFTS_ENABLED", False):
        logger.info("occasion_sweep_disabled")
        return {"enabled": False, "issued": 0, "skipped": 0, "failed": 0}

    terms = gift_terms()
    if lead_days is None:
        lead_days = terms.lead_days
    target = _target_date(lead_days)

    event_for = {
        "birthday": NotificationEvent.CUSTOMER_BIRTHDAY,
        "anniversary": NotificationEvent.CUSTOMER_ANNIVERSARY,
    }

    issued = skipped = failed = 0

    for occasion, field in OCCASION_FIELDS:
        for user in _matches_for(field=field, target=target).iterator(chunk_size=200):
            try:
                occasion_date = getattr(user, field)
                # The occasion's date *this* year, which is what the coupon
                # window and the year key are built from. A 1990 birthday is a
                # 2026 occasion.
                this_year = occasion_date.replace(year=target.year)
            except ValueError:
                # 29 Feb in a non-leap year — celebrate on 1 March.
                this_year = date(target.year, 3, 1)
            except AttributeError:
                continue

            if dry_run:
                skipped += 1
                logger.info(
                    "occasion_sweep_dry_run",
                    user_id=str(user.id), occasion=occasion, occasion_date=str(this_year),
                )
                continue

            try:
                coupon, created = issue_occasion_coupon(
                    user=user, occasion=occasion, occasion_date=this_year
                )
            except Exception as exc:  # noqa: BLE001
                failed += 1
                logger.exception(
                    "occasion_coupon_failed",
                    user_id=str(user.id), occasion=occasion, error=str(exc),
                )
                continue

            if coupon is None:
                failed += 1
                continue
            if not created:
                # Already issued this year. Do not re-send the email: a second
                # birthday email is worse than none.
                skipped += 1
                continue

            issued += 1
            _send_occasion_email(
                user=user,
                coupon=coupon,
                occasion=occasion,
                occasion_date=this_year,
                event=event_for[occasion],
                terms=terms,
            )

    logger.info(
        "occasion_sweep_done",
        target=str(target), lead_days=lead_days,
        issued=issued, skipped=skipped, failed=failed, dry_run=dry_run,
    )
    return {
        "enabled": True,
        "target": str(target),
        "lead_days": lead_days,
        "issued": issued,
        "skipped": skipped,
        "failed": failed,
        "dry_run": dry_run,
    }


def _send_occasion_email(*, user, coupon, occasion, occasion_date, event, terms) -> None:
    """
    Mention the gift. Never raises: the coupon is already theirs.
    """
    from apps.features import services as feature_services
    from apps.notifications.services.notification_service import trigger_event

    base = str(
        feature_services.get_setting("site.frontend_url", default="https://aurorablings.com")
        or "https://aurorablings.com"
    ).rstrip("/")

    try:
        trigger_event(
            event=event,
            context={
                "customer_name": user.get_full_name() or "there",
                "user_name": user.get_full_name() or "there",
                "occasion": occasion,
                "occasion_label": "birthday" if occasion == "birthday" else "anniversary",
                "occasion_date": occasion_date.strftime("%d %B"),
                "coupon_code": coupon.code,
                "discount_percent": str(terms.percent),
                "max_discount": str(terms.max_discount),
                "min_order_value": str(terms.min_order_value),
                "expires_on": timezone.localtime(coupon.end_date).strftime("%d %B %Y"),
                "shop_url": f"{base}/products",
            },
            recipient_user=user,
            recipient_email=user.email,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "occasion_email_failed",
            user_id=str(user.id), occasion=occasion, code=coupon.code, error=str(exc),
        )
