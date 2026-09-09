"""
Turning a walk-in into a customer.

The tests that matter are the ones about *not* doing it: not creating a duplicate,
not merging two people, not emailing a stranger, and not creating anything before
the money has landed.
"""

from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from apps.accounts import customer_linking
from apps.accounts.models import User, UserRole
from apps.orders.models import Order, OrderStatus, PaymentStatus, SalesChannel


def walkin_order(**kwargs):
    defaults = dict(
        status=OrderStatus.PLACED, payment_status=PaymentStatus.PENDING,
        subtotal=Decimal("2499.00"), grand_total=Decimal("2499.00"),
        channel=SalesChannel.POS, contact_name="Anita Sahoo", contact_phone="9876543210",
        guest_email="anita.sahoo@example.com",
    )
    defaults.update(kwargs)
    return Order.objects.create(**defaults)


class DedupeTests(TestCase):

    def test_a_returning_customer_is_linked_not_duplicated(self):
        existing = User.objects.create_user(
            email="anita.sahoo@example.com", password="x", first_name="Anita", last_name="S",
            phone="9876543210", role=UserRole.CUSTOMER,
        )
        order = walkin_order()

        result = customer_linking.link_or_create_customer(
            order=order, name="Anita", phone="9876543210", email="anita.sahoo@example.com",
        )
        order.refresh_from_db()

        self.assertFalse(result.created)
        self.assertEqual(result.user, existing)
        self.assertEqual(order.user_id, existing.id)
        self.assertEqual(User.objects.count(), 1)

    def test_phone_is_checked_before_email(self):
        """Phone is the identity at a counter; a mistyped email must not create a
        second account for someone already known by their number."""
        existing = User.objects.create_user(
            email="anita@example.com", password="x", first_name="Anita", last_name="S",
            phone="9876543210", role=UserRole.CUSTOMER,
        )
        order = walkin_order(guest_email="anita.typo@example.com")

        result = customer_linking.link_or_create_customer(
            order=order, phone="9876543210", email="anita.typo@example.com",
        )
        self.assertEqual(result.user, existing)
        self.assertFalse(result.created)

    def test_a_phone_email_conflict_is_left_for_a_human(self):
        """Two different people. Merging automatically is how one customer ends
        up reading another's order history."""
        by_phone = User.objects.create_user(
            email="mother@example.com", password="x", first_name="M", last_name="S",
            phone="9876543210", role=UserRole.CUSTOMER,
        )
        User.objects.create_user(
            email="daughter@example.com", password="x", first_name="D", last_name="S",
            role=UserRole.CUSTOMER,
        )
        order = walkin_order(guest_email="daughter@example.com")

        result = customer_linking.link_or_create_customer(
            order=order, phone="9876543210", email="daughter@example.com",
        )

        self.assertTrue(result.conflict)
        self.assertEqual(User.objects.count(), 2)
        order.refresh_from_db()
        self.assertEqual(order.user_id, by_phone.id)

    def test_a_shared_phone_number_is_a_conflict_not_a_guess(self):
        for email in ("a@example.com", "b@example.com"):
            User.objects.create_user(
                email=email, password="x", first_name="A", last_name="B",
                phone="9876543210", role=UserRole.CUSTOMER,
            )
        order = walkin_order(guest_email="")

        result = customer_linking.link_or_create_customer(order=order, phone="9876543210")
        self.assertTrue(result.conflict)

    def test_no_email_means_no_account_and_that_is_fine(self):
        order = walkin_order(guest_email="")
        result = customer_linking.link_or_create_customer(
            order=order, name="Walk-in", phone="9876543210", email="",
        )

        self.assertFalse(result.created)
        self.assertEqual(User.objects.count(), 0)
        order.refresh_from_db()
        self.assertEqual(order.contact_phone, "9876543210")


class AccountCreationTests(TestCase):

    def test_a_new_customer_gets_an_account_with_no_usable_password(self):
        order = walkin_order()
        result = customer_linking.link_or_create_customer(
            order=order, name="Anita Sahoo", phone="9876543210",
            email="anita.sahoo@example.com",
        )

        self.assertTrue(result.created)
        self.assertFalse(result.user.has_usable_password())
        self.assertEqual(result.user.role, UserRole.CUSTOMER)
        self.assertEqual(result.user.phone, "9876543210")

    def test_the_welcome_token_works_with_the_existing_reset_endpoint(self):
        """One token system, not two. An expired welcome falls back to the
        ordinary forgot-password flow with no support call."""
        from apps.accounts.services import confirm_password_reset

        order = walkin_order()
        result = customer_linking.link_or_create_customer(
            order=order, phone="9876543210", email="anita.sahoo@example.com",
        )
        token = customer_linking.issue_welcome_token(result.user)

        confirm_password_reset(token=token, new_password="ChosenByHer1")
        result.user.refresh_from_db()

        self.assertTrue(result.user.has_usable_password())
        self.assertTrue(result.user.check_password("ChosenByHer1"))

    @patch("apps.notifications.tasks.trigger_event_task.delay")
    def test_an_existing_customer_is_not_welcomed_again(self, mock_send):
        User.objects.create_user(
            email="anita.sahoo@example.com", password="x", first_name="A", last_name="S",
            phone="9876543210", role=UserRole.CUSTOMER,
        )
        order = walkin_order()
        result = customer_linking.link_or_create_customer(
            order=order, phone="9876543210", email="anita.sahoo@example.com",
        )
        if result.created:
            customer_linking.send_welcome(user=result.user, order=order)

        mock_send.assert_not_called()


class SettlementTimingTests(TestCase):
    """The account is created when the money lands — not before."""

    @patch("apps.accounts.tasks.link_customer_for_order_task.delay")
    def test_nothing_is_created_while_the_sale_is_unpaid(self, mock_task):
        walkin_order()
        mock_task.assert_not_called()
        self.assertEqual(User.objects.count(), 0)

    @patch("apps.accounts.tasks.link_customer_for_order_task.delay")
    def test_settlement_queues_the_link(self, mock_task):
        from apps.payments import tender_service
        from apps.payments.models import TenderMethod

        order = walkin_order()
        tender_service.record_tender(
            order=order, method=TenderMethod.CASH, amount_applied=Decimal("2499.00"),
        )
        order.refresh_from_db()

        self.assertEqual(order.payment_status, PaymentStatus.PAID)
        mock_task.assert_called_once()
        self.assertEqual(mock_task.call_args.kwargs["order_id"], str(order.id))


class MessyPhoneFormatTests(TestCase):
    """
    User.phone is free text with no normalisation anywhere, so the same customer
    can be on file half a dozen ways. An exact match finds one and misses the
    rest — which at a counter reads as "not in the system", and staff duly create
    a duplicate of a regular.
    """

    def setUp(self):
        self.stored_as = {}
        for i, stored in enumerate([
            "9876543210",
            "+919876543211",
            "+91 9876543212",
            "09876543213",
            "919876543214",
        ]):
            self.stored_as[stored] = User.objects.create_user(
                email=f"c{i}@example.com", password="x", first_name="C", last_name=str(i),
                phone=stored, role=UserRole.CUSTOMER,
            )

    def test_every_stored_shape_is_found_by_the_bare_number(self):
        for stored, user in self.stored_as.items():
            typed = customer_linking.phone_digits(stored)
            result = customer_linking.find_customer(phone=typed)
            self.assertEqual(
                result.user, user,
                f"{typed} typed at the counter did not find the customer stored as {stored!r}",
            )

    def test_phone_digits_takes_the_last_ten(self):
        self.assertEqual(customer_linking.phone_digits("+91 98765 43210"), "9876543210")
        self.assertEqual(customer_linking.phone_digits("09876543210"), "9876543210")
        self.assertEqual(customer_linking.phone_digits("98765"), "98765")

    def test_the_normalise_command_cleans_what_lookup_cannot(self):
        """Numbers with spaces inside them need the data fixed, not the query."""
        from io import StringIO

        from django.core.management import call_command

        spaced = User.objects.create_user(
            email="spaced@example.com", password="x", first_name="S", last_name="P",
            phone="+91 98765 43299", role=UserRole.CUSTOMER,
        )
        self.assertIsNone(customer_linking.find_customer(phone="9876543299").user)

        call_command("normalize_customer_phones", stdout=StringIO())
        spaced.refresh_from_db()

        self.assertEqual(spaced.phone, "9876543299")
        self.assertEqual(customer_linking.find_customer(phone="9876543299").user, spaced)


class AddressPhoneTests(TestCase):
    """
    Most customers never fill in User.phone — they type a number into checkout,
    which saves it on the Address. Searching only the user record makes a regular
    look like a stranger at the counter.
    """

    def setUp(self):
        from apps.accounts.models import Address

        self.user = User.objects.create_user(
            email="regular@example.com", password="x", first_name="Reg", last_name="Ular",
            role=UserRole.CUSTOMER,
        )
        self.assertEqual(self.user.phone, "")
        Address.objects.create(
            user=self.user, full_name="Reg Ular", line1="1 Street", city="Bhubaneswar",
            state="Odisha", postal_code="751001", country="IN", phone="9876543210",
        )

    def test_a_number_saved_only_on_an_address_is_found(self):
        result = customer_linking.find_customer(phone="9876543210")
        self.assertEqual(result.user, self.user)
        self.assertIn("address", result.reason)

    def test_the_number_is_promoted_onto_the_account_for_next_time(self):
        customer_linking.find_customer(phone="9876543210")
        self.user.refresh_from_db()
        self.assertEqual(self.user.phone, "9876543210")
