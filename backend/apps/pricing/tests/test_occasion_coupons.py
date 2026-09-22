"""
Birthday / anniversary gift coupons.

The tests that matter here are the ones about *not* doing something: not
letting a stranger spend someone's gift, not issuing two coupons for one
birthday, and not quietly skipping the customers born on 29 February.
"""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import User, UserRole
from apps.pricing.coupons.models import Coupon, CouponOccasion
from apps.pricing.coupons.occasions import issue_occasion_coupon
from apps.pricing.coupons.services import CouponService
from apps.pricing.tasks import issue_occasion_coupons
from core.exceptions import ValidationError


def customer(email, **kwargs):
    return User.objects.create_user(
        email=email, password="x", first_name="Test", last_name="Customer",
        role=UserRole.CUSTOMER, **kwargs
    )


class OwnershipTests(TestCase):
    """A personal coupon is one customer's, and forwarding the code changes nothing."""

    def setUp(self):
        self.owner = customer("owner@example.com")
        self.stranger = customer("stranger@example.com")
        self.coupon, _ = issue_occasion_coupon(
            user=self.owner, occasion=CouponOccasion.BIRTHDAY, occasion_date=date.today(),
        )

    def test_a_stranger_cannot_redeem_it(self):
        with self.assertRaises(ValidationError):
            CouponService.validate_coupon(coupon=self.coupon, user=self.stranger, cart=None)

    def test_an_anonymous_shopper_cannot_redeem_it(self):
        with self.assertRaises(ValidationError):
            CouponService.validate_coupon(coupon=self.coupon, user=None, cart=None)

    def test_the_rejection_does_not_confirm_the_code_is_real(self):
        """
        Someone who was forwarded a birthday code must not be able to tell a real
        code from a typo — "not yours" is itself an answer worth having.
        """
        with self.assertRaises(ValidationError) as ctx:
            CouponService.validate_coupon(coupon=self.coupon, user=self.stranger, cart=None)
        self.assertNotIn(self.coupon.code, str(ctx.exception))

    @patch("apps.pricing.coupons.services.calculate_cart_totals")
    def test_the_owner_can_redeem_it(self, totals):
        totals.return_value = {"subtotal": Decimal("2000.00")}
        # No exception is the assertion.
        CouponService.validate_coupon(coupon=self.coupon, user=self.owner, cart=object())

    @patch("apps.pricing.coupons.services.calculate_cart_totals")
    def test_ordinary_campaign_coupons_are_unaffected(self, totals):
        totals.return_value = {"subtotal": Decimal("2000.00")}
        now = timezone.now()
        public = Coupon.objects.create(
            code="DIWALI20", type="percentage", value=20,
            start_date=now - timedelta(days=1), end_date=now + timedelta(days=30),
        )
        CouponService.validate_coupon(coupon=public, user=None, cart=object())


class IdempotencyTests(TestCase):
    """The sweep will be retried. It must not cost a second discount when it is."""

    def test_issuing_twice_returns_the_same_coupon(self):
        user = customer("twice@example.com")
        first, created_first = issue_occasion_coupon(
            user=user, occasion=CouponOccasion.BIRTHDAY, occasion_date=date(2026, 6, 1),
        )
        second, created_second = issue_occasion_coupon(
            user=user, occasion=CouponOccasion.BIRTHDAY, occasion_date=date(2026, 6, 1),
        )

        self.assertTrue(created_first)
        self.assertFalse(created_second)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Coupon.objects.filter(assigned_user=user).count(), 1)

    def test_next_year_gets_its_own_coupon(self):
        user = customer("nextyear@example.com")
        issue_occasion_coupon(
            user=user, occasion=CouponOccasion.BIRTHDAY, occasion_date=date(2026, 6, 1),
        )
        _, created = issue_occasion_coupon(
            user=user, occasion=CouponOccasion.BIRTHDAY, occasion_date=date(2027, 6, 1),
        )
        self.assertTrue(created)
        self.assertEqual(Coupon.objects.filter(assigned_user=user).count(), 2)

    def test_birthday_and_anniversary_are_separate_gifts(self):
        user = customer("both@example.com")
        issue_occasion_coupon(
            user=user, occasion=CouponOccasion.BIRTHDAY, occasion_date=date(2026, 6, 1),
        )
        _, created = issue_occasion_coupon(
            user=user, occasion=CouponOccasion.ANNIVERSARY, occasion_date=date(2026, 6, 1),
        )
        self.assertTrue(created)


@override_settings(OCCASION_GIFTS_ENABLED=True, OCCASION_GIFT_LEAD_DAYS=3)
class SweepTests(TestCase):

    def setUp(self):
        # The sweep sends email through the notification engine; that is tested
        # elsewhere and an SMTP attempt here would only make these slow.
        patcher = patch("apps.pricing.tasks._send_occasion_email")
        self.send = patcher.start()
        self.addCleanup(patcher.stop)

    def _due_date(self, lead_days=3):
        return timezone.localdate() + timedelta(days=lead_days)

    def test_it_finds_the_customer_whose_birthday_is_the_lead_days_away(self):
        due = self._due_date()
        user = customer("due@example.com", date_of_birth=date(1990, due.month, due.day))
        customer("notdue@example.com", date_of_birth=due + timedelta(days=10))

        result = issue_occasion_coupons()

        self.assertEqual(result["issued"], 1)
        self.assertEqual(Coupon.objects.filter(assigned_user=user).count(), 1)
        self.assertEqual(self.send.call_count, 1)

    def test_the_year_is_ignored(self):
        """An anniversary is a month and a day. 1998 and 2019 are both due today+3."""
        due = self._due_date()
        customer("old@example.com", anniversary_date=date(1998, due.month, due.day))
        customer("recent@example.com", anniversary_date=date(2019, due.month, due.day))

        self.assertEqual(issue_occasion_coupons()["issued"], 2)

    def test_running_it_again_the_same_day_issues_nothing_and_re_sends_nothing(self):
        due = self._due_date()
        customer("repeat@example.com", date_of_birth=date(1990, due.month, due.day))

        issue_occasion_coupons()
        second = issue_occasion_coupons()

        self.assertEqual(second["issued"], 0)
        self.assertEqual(second["skipped"], 1)
        # The important half: one birthday, one email.
        self.assertEqual(self.send.call_count, 1)

    def test_a_customer_with_no_email_is_skipped(self):
        """Nothing to send to. The date stays on file for the year they give us one."""
        due = self._due_date()
        user = customer("noemail@example.com", date_of_birth=date(1990, due.month, due.day))
        User.objects.filter(pk=user.pk).update(email="")

        self.assertEqual(issue_occasion_coupons()["issued"], 0)

    def test_an_inactive_customer_is_skipped(self):
        due = self._due_date()
        user = customer("gone@example.com", date_of_birth=date(1990, due.month, due.day))
        User.objects.filter(pk=user.pk).update(is_active=False)

        self.assertEqual(issue_occasion_coupons()["issued"], 0)

    def test_dry_run_writes_nothing(self):
        due = self._due_date()
        customer("dry@example.com", date_of_birth=date(1990, due.month, due.day))

        result = issue_occasion_coupons(dry_run=True)

        self.assertEqual(result["issued"], 0)
        self.assertEqual(Coupon.objects.count(), 0)
        self.assertEqual(self.send.call_count, 0)

    @override_settings(OCCASION_GIFTS_ENABLED=False)
    def test_the_switch_actually_switches_it_off(self):
        due = self._due_date()
        customer("off@example.com", date_of_birth=date(1990, due.month, due.day))

        result = issue_occasion_coupons()

        self.assertFalse(result["enabled"])
        self.assertEqual(Coupon.objects.count(), 0)


class LeapDayTests(TestCase):
    """
    29 February birthdays are the bug nobody notices for four years.

    The sweep folds them into 1 March in non-leap years, so these customers get
    their gift annually like everyone else.
    """

    @override_settings(OCCASION_GIFTS_ENABLED=True, OCCASION_GIFT_LEAD_DAYS=0)
    @patch("apps.pricing.tasks._send_occasion_email")
    @patch("apps.pricing.tasks._target_date")
    def test_a_29_february_birthday_is_swept_on_1_march_in_a_common_year(self, target, _send):
        target.return_value = date(2027, 3, 1)  # 2027 is not a leap year
        user = customer("leap@example.com", date_of_birth=date(2000, 2, 29))

        result = issue_occasion_coupons()

        self.assertEqual(result["issued"], 1)
        coupon = Coupon.objects.get(assigned_user=user)
        self.assertEqual(coupon.occasion_year, 2027)

    @override_settings(OCCASION_GIFTS_ENABLED=True, OCCASION_GIFT_LEAD_DAYS=0)
    @patch("apps.pricing.tasks._send_occasion_email")
    @patch("apps.pricing.tasks._target_date")
    def test_it_is_not_swept_twice_in_a_leap_year(self, target, _send):
        """
        In a leap year 29 February is its own day, so 1 March must not pick the
        same customer up again — that would be two gifts in two days.
        """
        target.return_value = date(2028, 3, 1)  # 2028 IS a leap year
        customer("leap2@example.com", date_of_birth=date(2000, 2, 29))

        self.assertEqual(issue_occasion_coupons()["issued"], 0)
