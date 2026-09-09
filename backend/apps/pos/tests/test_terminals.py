"""
Terminal management.

Staff run a counter; only an admin decides what the counters are. The rest of
this file is about the two ways deleting a terminal would quietly damage the
books, and the refusals that stop it.
"""

from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User, UserRole
from apps.orders.models import Order, OrderStatus, PaymentStatus
from apps.pos import services
from apps.pos.models import POSTerminal, ShiftStatus


class TerminalManagementTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email="owner@aurorablings.com", password="x", first_name="S", last_name="S",
            role=UserRole.ADMIN,
        )
        self.staff = User.objects.create_user(
            email="priya@aurorablings.com", password="x", first_name="P", last_name="S",
            role=UserRole.STAFF,
        )
        self.terminal = POSTerminal.objects.create(code="STALL-01", name="Stall table")

    def list_url(self):
        return reverse("pos:terminals")

    def detail_url(self, terminal=None):
        return reverse("pos:terminal-detail", kwargs={"terminal_id": (terminal or self.terminal).id})

    # ── who may do what ─────────────────────────────────────

    def test_anonymous_sees_nothing(self):
        self.assertIn(self.client.get(self.list_url()).status_code, (401, 403))

    def test_staff_can_list_but_not_create(self):
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.get(self.list_url()).status_code, 200)
        response = self.client.post(self.list_url(), {"code": "STALL-02", "name": "Second"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(POSTerminal.objects.count(), 1)

    def test_staff_can_neither_edit_nor_delete(self):
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.patch(self.detail_url(), {"name": "Renamed"}).status_code, 403)
        self.assertEqual(self.client.delete(self.detail_url()).status_code, 403)

    def test_admin_creates_a_terminal_and_the_code_is_normalised(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            self.list_url(), {"code": " stall-02 ", "name": "  Second table  ", "location": "Bhubaneswar"},
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["code"], "STALL-02")
        self.assertEqual(response.data["name"], "Second table")

    def test_a_duplicate_code_in_another_case_is_refused(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(self.list_url(), {"code": "stall-01", "name": "Clash"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(POSTerminal.objects.count(), 1)

    # ── what the counter sees ───────────────────────────────

    def test_the_counter_never_sees_an_inactive_terminal(self):
        POSTerminal.objects.create(code="OLD-01", name="Retired", is_active=False)
        self.client.force_authenticate(self.staff)

        # No parameter: the shift gate's call.
        codes = [t["code"] for t in self.client.get(self.list_url()).data]
        self.assertEqual(codes, ["STALL-01"])

        # Staff asking for everything still get only the active ones.
        codes = [t["code"] for t in self.client.get(self.list_url(), {"include_inactive": "true"}).data]
        self.assertEqual(codes, ["STALL-01"])

    def test_an_admin_asking_for_everything_gets_the_inactive_ones(self):
        POSTerminal.objects.create(code="OLD-01", name="Retired", is_active=False)
        self.client.force_authenticate(self.admin)
        codes = sorted(t["code"] for t in self.client.get(self.list_url(), {"include_inactive": "true"}).data)
        self.assertEqual(codes, ["OLD-01", "STALL-01"])

    # ── the refusals ────────────────────────────────────────

    def test_a_terminal_with_an_open_shift_cannot_be_deactivated(self):
        services.open_shift(terminal=self.terminal, staff=self.staff, opening_float=Decimal("2000"))
        self.client.force_authenticate(self.admin)

        response = self.client.patch(self.detail_url(), {"is_active": False})

        self.assertEqual(response.status_code, 409, response.data)
        self.terminal.refresh_from_db()
        self.assertTrue(self.terminal.is_active)

    def test_a_terminal_that_has_traded_cannot_be_deleted(self):
        shift = services.open_shift(
            terminal=self.terminal, staff=self.staff, opening_float=Decimal("2000"),
        )
        Order.objects.create(
            guest_email="walkin@example.com",
            status=OrderStatus.PLACED, payment_status=PaymentStatus.PENDING,
            subtotal=Decimal("1850.00"), grand_total=Decimal("1850.00"),
            pos_shift=shift, pos_terminal=self.terminal,
        )
        self.client.force_authenticate(self.admin)

        response = self.client.delete(self.detail_url())

        self.assertEqual(response.status_code, 409, response.data)
        self.assertTrue(POSTerminal.objects.filter(pk=self.terminal.pk).exists())

    def test_a_terminal_that_never_traded_can_be_deleted(self):
        spare = POSTerminal.objects.create(code="SPARE-01", name="Never used")
        self.client.force_authenticate(self.admin)

        response = self.client.delete(self.detail_url(spare))

        self.assertEqual(response.status_code, 204)
        self.assertFalse(POSTerminal.objects.filter(pk=spare.pk).exists())

    def test_deactivating_an_idle_terminal_is_allowed_and_keeps_its_history(self):
        shift = services.open_shift(
            terminal=self.terminal, staff=self.staff, opening_float=Decimal("2000"),
        )
        shift.status = ShiftStatus.CLOSED
        shift.save(update_fields=["status"])
        self.client.force_authenticate(self.admin)

        response = self.client.patch(self.detail_url(), {"is_active": False})

        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(response.data["is_active"])
        self.assertEqual(response.data["shift_count"], 1)
