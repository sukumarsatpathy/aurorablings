"""
Endpoint-level checks.

Mostly one question: can a device that isn't a logged-in staff member move money?
"""

from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User, UserRole
from apps.orders.models import Order, OrderStatus, PaymentStatus
from apps.pos import services
from apps.pos.models import POSTerminal


class POSApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.staff = User.objects.create_user(
            email="priya@aurorablings.com", password="x", first_name="P", last_name="S",
            role=UserRole.STAFF,
        )
        self.customer = User.objects.create_user(
            email="shopper@example.com", password="x", first_name="A", last_name="B",
            role=UserRole.CUSTOMER,
        )
        self.terminal = POSTerminal.objects.create(code="STALL-01", name="Stall")
        self.shift = services.open_shift(
            terminal=self.terminal, staff=self.staff, opening_float=Decimal("2000"),
        )
        self.order = Order.objects.create(
            guest_email="walkin@example.com",
            status=OrderStatus.PLACED, payment_status=PaymentStatus.PENDING,
            subtotal=Decimal("1850.00"), grand_total=Decimal("1850.00"),
            pos_shift=self.shift, pos_terminal=self.terminal,
        )

    def url(self):
        return reverse("pos:cash-tender", kwargs={"shift_id": self.shift.id})

    def payload(self, applied="1850.00", received="2000.00"):
        return {"order": str(self.order.id), "amount_applied": applied, "cash_received": received}

    def test_anonymous_cannot_take_cash(self):
        self.assertIn(self.client.post(self.url(), self.payload()).status_code, (401, 403))

    def test_a_customer_account_cannot_take_cash(self):
        self.client.force_authenticate(self.customer)
        self.assertEqual(self.client.post(self.url(), self.payload()).status_code, 403)

    def test_staff_takes_cash_and_gets_the_change_back(self):
        self.client.force_authenticate(self.staff)
        response = self.client.post(self.url(), self.payload())

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["change_given"], "150.00")
        self.assertEqual(response.data["balance_due"], "0.00")
        self.assertEqual(response.data["order_payment_status"], PaymentStatus.PAID)
        self.assertEqual(response.data["expected_cash_now"], "3850.00")

    def test_over_tender_is_refused_with_a_conflict(self):
        """The counter asking to apply more than the sale is worth is a conflict,
        not a validation error — the request is fine, the money isn't."""
        self.client.force_authenticate(self.staff)
        response = self.client.post(self.url(), self.payload(applied="5000.00", received="5000.00"))
        self.assertEqual(response.status_code, 409, response.data)
        self.assertEqual(self.order.tenders.count(), 0)

    def test_close_conflicts_while_a_part_paid_order_is_open(self):
        self.client.force_authenticate(self.staff)
        self.client.post(self.url(), self.payload(applied="1000.00", received="1000.00"))

        close_url = reverse("pos:shift-close", kwargs={"shift_id": self.shift.id})
        blocked = self.client.post(close_url, {"counted_cash": "3000.00"})
        self.assertEqual(blocked.status_code, 409)

        forced = self.client.post(close_url, {"counted_cash": "3000.00", "force": True})
        self.assertEqual(forced.status_code, 200, forced.data)
        self.assertEqual(forced.data["variance"], "0.00")
