"""
Website guest checkout.

What must hold:
  - a guest can place a prepaid (Razorpay) order without logging in, but only
    with a name and phone the courier can use, and only while the switch is on
  - choosing guest means no account is created for them after payment
  - the guest token opens exactly one ownerless order — never someone else's,
    never a registered customer's
  - without a token or a login, these endpoints still answer 401, as before
"""

from decimal import Decimal
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.features.models import AppSetting
from apps.orders import guest_access, services
from apps.orders.models import Order, OrderStatus, PaymentStatus
from apps.payments.models import PaymentTransaction, TransactionStatus
from core.exceptions import ValidationError

ADDRESS = {
    "full_name": "Asha Rao",
    "phone": "9876543210",
    "line1": "12 Temple Road",
    "city": "Puri",
    "state": "Odisha",
    "pincode": "752002",
    "country": "India",
}


def guest_order(**kwargs):
    defaults = dict(
        status=OrderStatus.PLACED, payment_status=PaymentStatus.PENDING,
        subtotal=Decimal("999.00"), grand_total=Decimal("999.00"),
        shipping_address=ADDRESS,
    )
    defaults.update(kwargs)
    return Order.objects.create(**defaults)


class GuestPlaceOrderRulesTests(TestCase):
    """The service-level guard, with the cart → order step stubbed out."""

    def setUp(self):
        cache.clear()
        self.placed = guest_order()

    def _place(self, **kwargs):
        args = dict(cart=object(), shipping_address=dict(ADDRESS), payment_method="razorpay")
        args.update(kwargs)
        with patch.object(services, "place_order", return_value=self.placed):
            return services.checkout_place_order(**args)

    def test_guest_can_place_a_prepaid_order(self):
        order, user = self._place(guest_checkout=True)
        self.assertIsNone(user)
        self.assertEqual(order.pk, self.placed.pk)

    def test_choosing_guest_turns_off_account_creation(self):
        self.assertTrue(self.placed.contact_wants_account)
        order, _ = self._place(guest_checkout=True, guest_email="asha@example.com")
        order.refresh_from_db()
        self.assertFalse(order.contact_wants_account)

    def test_email_is_optional_for_a_guest(self):
        order, _ = self._place(guest_checkout=True, guest_email="")
        self.assertEqual(order.pk, self.placed.pk)

    def test_guest_still_needs_a_name_and_phone(self):
        with self.assertRaises(ValidationError):
            self._place(guest_checkout=True, shipping_address={**ADDRESS, "full_name": ""})
        with self.assertRaises(ValidationError):
            self._place(guest_checkout=True, shipping_address={**ADDRESS, "phone": "98765"})

    def test_without_the_guest_flag_prepaid_still_needs_a_login(self):
        with self.assertRaises(ValidationError):
            self._place()

    def test_switch_off_restores_the_old_rule(self):
        AppSetting.objects.update_or_create(
            key="checkout_guest_enabled", defaults={"value": "false", "value_type": "boolean"},
        )
        with self.assertRaises(ValidationError):
            self._place(guest_checkout=True)

    def test_guest_flag_is_ignored_for_a_logged_in_customer(self):
        user = User.objects.create_user(email="a@example.com", password="x", first_name="A", last_name="R")
        with patch.object(services.account_services, "save_checkout_address"):
            order, resolved = self._place(guest_checkout=True, user=user)
        self.assertEqual(resolved, user)
        order.refresh_from_db()
        # Nothing about the guest path touched a registered customer's order.
        self.assertTrue(order.contact_wants_account)


class GuestTokenTests(TestCase):
    def test_no_token_for_an_owned_order(self):
        user = User.objects.create_user(email="a@example.com", password="x", first_name="A", last_name="R")
        self.assertEqual(guest_access.issue_token(guest_order(user=user)), "")

    def test_token_round_trip(self):
        order = guest_order()
        token = guest_access.issue_token(order)

        class Req:
            headers = {guest_access.HEADER: token}
            data = {}

        self.assertEqual(guest_access.token_order_id(Req), str(order.id))

    def test_tampered_token_is_rejected(self):
        order = guest_order()
        token = guest_access.issue_token(order) + "x"

        class Req:
            headers = {guest_access.HEADER: token}
            data = {}

        self.assertIsNone(guest_access.token_order_id(Req))


class GuestOrderAccessApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.order = guest_order()
        self.token = guest_access.issue_token(self.order)

    def _auth(self, token=None):
        self.client.credentials(HTTP_X_GUEST_ORDER_TOKEN=token or self.token)

    # ── order detail ──────────────────────────────────────────

    def test_anonymous_without_token_is_still_401(self):
        response = self.client.get(reverse("orders:detail", args=[self.order.id]))
        self.assertEqual(response.status_code, 401)

    def test_guest_reads_own_order(self):
        self._auth()
        response = self.client.get(reverse("orders:detail", args=[self.order.id]))
        self.assertEqual(response.status_code, 200)

    def test_token_for_one_order_does_not_open_another(self):
        other = guest_order()
        self._auth()
        response = self.client.get(reverse("orders:detail", args=[other.id]))
        self.assertEqual(response.status_code, 404)

    def test_token_cannot_reach_a_customers_order(self):
        user = User.objects.create_user(email="a@example.com", password="x", first_name="A", last_name="R")
        owned = guest_order(user=user)
        # Forge a token for it the only way possible: by signing its id ourselves.
        from django.core import signing
        forged = signing.dumps({"o": str(owned.id)}, salt=guest_access.SALT, compress=True)
        self._auth(forged)
        response = self.client.get(reverse("orders:detail", args=[owned.id]))
        self.assertEqual(response.status_code, 404)

    def test_logged_in_customer_unchanged(self):
        user = User.objects.create_user(email="a@example.com", password="x", first_name="A", last_name="R")
        owned = guest_order(user=user)
        self.client.force_authenticate(user)
        self.assertEqual(self.client.get(reverse("orders:detail", args=[owned.id])).status_code, 200)
        self.assertEqual(self.client.get(reverse("orders:detail", args=[self.order.id])).status_code, 404)

    # ── cancel ───────────────────────────────────────────────

    def test_guest_can_cancel_own_unpaid_order(self):
        self._auth()
        response = self.client.post(reverse("orders:cancel", args=[self.order.id]), {}, format="json")
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.CANCELLED)

    def test_guest_cannot_cancel_a_paid_order(self):
        self.order.payment_status = PaymentStatus.PAID
        self.order.status = OrderStatus.PAID
        self.order.save(update_fields=["payment_status", "status"])
        self._auth()
        response = self.client.post(reverse("orders:cancel", args=[self.order.id]), {}, format="json")
        self.assertEqual(response.status_code, 409)

    def test_cancel_without_token_is_401(self):
        response = self.client.post(reverse("orders:cancel", args=[self.order.id]), {}, format="json")
        self.assertEqual(response.status_code, 401)

    # ── payments ─────────────────────────────────────────────

    def test_guest_can_create_a_razorpay_order(self):
        txn = PaymentTransaction.objects.create(
            order=self.order, provider="razorpay", status=TransactionStatus.CREATED,
            amount=Decimal("999.00"), razorpay_order_id="order_TEST1", raw_response={"key_id": "rzp_test"},
        )
        self._auth()
        with patch("apps.payments.services.create_checkout_order", return_value=txn) as created:
            response = self.client.post(
                reverse("payments:create-order"),
                {"order_id": str(self.order.id), "amount": "999.00", "currency": "INR"},
                format="json",
            )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertIsNone(created.call_args.kwargs["initiated_by"])

    def test_create_order_without_token_is_401(self):
        response = self.client.post(
            reverse("payments:create-order"),
            {"order_id": str(self.order.id), "amount": "999.00"},
            format="json",
        )
        self.assertEqual(response.status_code, 401)

    def test_verify_refuses_a_token_for_another_order(self):
        other = guest_order()
        PaymentTransaction.objects.create(
            order=other, provider="razorpay", status=TransactionStatus.CREATED,
            amount=Decimal("999.00"), razorpay_order_id="order_OTHER",
        )
        self._auth()
        response = self.client.post(
            reverse("payments:verify"),
            {"razorpay_order_id": "order_OTHER", "razorpay_payment_id": "pay_X", "razorpay_signature": "sig"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)

    def test_verify_with_own_token_reaches_the_verifier(self):
        txn = PaymentTransaction.objects.create(
            order=self.order, provider="razorpay", status=TransactionStatus.CREATED,
            amount=Decimal("999.00"), razorpay_order_id="order_MINE",
        )
        txn.status = TransactionStatus.SUCCESS
        self._auth()
        with patch("apps.payments.services.verify_checkout_payment", return_value=txn) as verified:
            response = self.client.post(
                reverse("payments:verify"),
                {"razorpay_order_id": "order_MINE", "razorpay_payment_id": "pay_X", "razorpay_signature": "sig"},
                format="json",
            )
        self.assertEqual(response.status_code, 200, response.content)
        verified.assert_called_once()

    def test_guest_can_reconcile_own_order(self):
        self._auth()
        with patch("apps.payments.services.reconcile_order_payment", return_value=None):
            response = self.client.post(
                reverse("payments:reconcile"), {"order_id": str(self.order.id)}, format="json",
            )
        self.assertEqual(response.status_code, 200)

    # ── placing ──────────────────────────────────────────────

    def test_place_order_returns_a_guest_token_for_guests_only(self):
        with patch("apps.orders.views._resolve_cart_for_order", return_value=object()), \
             patch("apps.orders.views.services.checkout_place_order", return_value=(self.order, None)) as placed:
            response = self.client.post(
                reverse("orders:place"),
                {
                    "shipping_address": ADDRESS, "payment_method": "razorpay",
                    "guest_checkout": True, "guest_email": "",
                },
                format="json",
            )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertTrue(placed.call_args.kwargs["guest_checkout"])
        token = response.json()["data"]["guest_token"]
        self.assertTrue(token)

        # And the token works for this order.
        self._auth(token)
        self.assertEqual(self.client.get(reverse("orders:detail", args=[self.order.id])).status_code, 200)
