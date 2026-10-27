"""
Putting full customer details on an order from the admin panel.

What must hold:
  - picking an existing customer links the order to that account
  - typed details are stored on the order (name, phone, email)
  - typed details that match an existing customer link to them, never a duplicate
  - a new account is created only when asked, and only with an email
  - "save address" puts the delivery address in the linked customer's book
"""

from decimal import Decimal
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import Address, User, UserRole
from apps.orders.models import Order, OrderStatus, PaymentStatus

ADDRESS = {
    "full_name": "Asha Rao", "phone": "9876543210",
    "line1": "12 Temple Road", "city": "Puri", "state": "Odisha",
    "pincode": "752002", "country": "India",
}


class AdminCustomerDetailsTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_user(
            email="admin@aurorablings.com", password="x", first_name="A", last_name="D",
            role=UserRole.ADMIN,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.order = Order.objects.create(
            status=OrderStatus.PLACED, payment_status=PaymentStatus.PENDING,
            subtotal=Decimal("999.00"), grand_total=Decimal("999.00"),
            shipping_address=ADDRESS,
        )
        self.url = reverse("orders:admin-detail", args=[self.order.id])

    def test_select_existing_customer_links_the_order(self):
        customer = User.objects.create_user(
            email="asha@example.com", password="x", first_name="Asha", last_name="Rao",
        )
        response = self.client.patch(
            self.url,
            {"user_id": str(customer.id), "contact_name": "Asha Rao", "contact_phone": "9876543210"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.order.refresh_from_db()
        customer.refresh_from_db()
        self.assertEqual(self.order.user_id, customer.id)
        self.assertEqual(self.order.contact_phone, "9876543210")
        # A phone they didn't have on file is kept.
        self.assertEqual(customer.phone, "9876543210")
        self.assertEqual(response.json()["data"]["customer_id"], str(customer.id))

    def test_typed_details_are_stored_on_the_order(self):
        response = self.client.patch(
            self.url,
            {"contact_name": "Walk In", "contact_phone": "9123456789", "guest_email": "walk@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.order.refresh_from_db()
        self.assertEqual(self.order.contact_name, "Walk In")
        self.assertEqual(self.order.contact_phone, "9123456789")
        self.assertEqual(self.order.guest_email, "walk@example.com")
        self.assertIsNone(self.order.user_id)

    def test_typed_phone_matching_a_customer_links_them(self):
        customer = User.objects.create_user(
            email="asha@example.com", password="x", first_name="Asha", last_name="Rao",
            phone="9876543210",
        )
        self.client.patch(self.url, {"contact_name": "Asha", "contact_phone": "9876543210"}, format="json")
        self.order.refresh_from_db()
        self.assertEqual(self.order.user_id, customer.id)
        self.assertEqual(User.objects.filter(role=UserRole.CUSTOMER).count(), 1)

    def test_account_is_created_only_when_asked(self):
        self.client.patch(
            self.url, {"contact_name": "New Person", "guest_email": "new@example.com"}, format="json",
        )
        self.assertFalse(User.objects.filter(email="new@example.com").exists())

        with patch("apps.accounts.customer_linking.send_welcome") as welcome:
            response = self.client.patch(
                self.url,
                {"contact_name": "New Person", "guest_email": "new@example.com", "create_account": True},
                format="json",
            )
        self.assertEqual(response.status_code, 200, response.content)
        user = User.objects.get(email="new@example.com")
        self.order.refresh_from_db()
        self.assertEqual(self.order.user_id, user.id)
        self.assertEqual(user.first_name, "New")
        welcome.assert_called_once()

    def test_save_address_to_profile(self):
        customer = User.objects.create_user(
            email="asha@example.com", password="x", first_name="Asha", last_name="Rao",
        )
        self.client.patch(
            self.url, {"user_id": str(customer.id), "save_address_to_profile": True}, format="json",
        )
        address = Address.objects.get(user=customer)
        self.assertEqual(address.line1, "12 Temple Road")
        self.assertEqual(address.postal_code, "752002")

    def test_bad_phone_is_rejected(self):
        response = self.client.patch(self.url, {"contact_phone": "12345"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_plain_status_edit_does_not_touch_the_customer(self):
        self.order.contact_name = "Keep Me"
        self.order.save(update_fields=["contact_name"])
        response = self.client.patch(self.url, {"notes": "gift wrap"}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.order.refresh_from_db()
        self.assertEqual(self.order.contact_name, "Keep Me")
        self.assertEqual(self.order.notes, "gift wrap")

    def test_customer_search_matches_phone(self):
        User.objects.create_user(
            email="asha@example.com", password="x", first_name="Asha", last_name="Rao",
            phone="9876543210",
        )
        response = self.client.get(reverse("accounts:admin-customer-list") + "?search=98765")
        self.assertEqual(response.status_code, 200, response.content)
        emails = [row["email"] for row in response.json()["data"]]
        self.assertIn("asha@example.com", emails)
