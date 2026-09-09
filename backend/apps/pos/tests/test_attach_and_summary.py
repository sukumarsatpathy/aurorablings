"""
Counter attribution, and the close-out figures.

The regression these exist for: every POS report reads channel / pos_shift /
pos_terminal, and for a while nothing wrote them. The part-paid list was empty,
the shift-close guard never fired, and the tests passed because they set the
fields by hand. These deliberately do not.
"""

from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User, UserRole
from apps.orders.models import Order, OrderStatus, PaymentStatus, SalesChannel
from apps.payments.providers.base import QRCodeResult
from apps.pos import collection_service, services
from apps.pos.models import CashMovementType, POSTerminal


class CounterAttributionTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            email="priya@aurorablings.com", password="x", first_name="P", last_name="S",
            role=UserRole.STAFF,
        )
        self.terminal = POSTerminal.objects.create(code="STALL-01", name="Stall")
        self.shift = services.open_shift(
            terminal=self.terminal, staff=self.staff, opening_float=Decimal("2000"),
        )

    def plain_order(self, total="4798.00"):
        """An order with nothing POS about it — as the order pipeline creates it."""
        return Order.objects.create(
            guest_email="walkin@example.com",
            status=OrderStatus.PLACED, payment_status=PaymentStatus.PENDING,
            subtotal=Decimal(total), grand_total=Decimal(total),
        )

    def test_taking_cash_stamps_the_sale_as_a_counter_sale(self):
        order = self.plain_order()
        self.assertEqual(order.channel, SalesChannel.ONLINE)

        services.take_cash_tender(
            order=order, shift=self.shift, staff=self.staff, amount_applied=Decimal("2000.00"),
        )
        order.refresh_from_db()

        self.assertEqual(order.channel, SalesChannel.POS)
        self.assertEqual(order.pos_shift_id, self.shift.id)
        self.assertEqual(order.pos_terminal_id, self.terminal.id)
        self.assertEqual(order.created_by_staff_id, self.staff.id)

    def test_a_part_paid_counter_sale_is_discoverable_without_being_hand_stamped(self):
        """The bug this file exists for: the close guard and the counter's
        part-paid list were both reading fields nobody wrote."""
        order = self.plain_order()
        services.take_cash_tender(
            order=order, shift=self.shift, staff=self.staff, amount_applied=Decimal("2000.00"),
        )

        self.assertEqual([o.id for o in services.open_part_paid_orders(self.shift)], [order.id])
        self.assertEqual([o.id for o in services.part_paid_orders(shift=self.shift)], [order.id])

        with self.assertRaises(services.ShiftError):
            services.close_shift(shift=self.shift, staff=self.staff, counted_cash=Decimal("4000"))

    @patch("apps.payments.providers.razorpay.RazorpayProvider.create_qr_code")
    def test_a_upi_only_counter_sale_is_stamped_too(self, mock_qr):
        """No cash leg means take_cash_tender never runs, so the QR path has to
        do the stamping or the sale is invisible to every POS report."""
        mock_qr.return_value = QRCodeResult(
            success=True, provider_ref="qr_X", image_url="https://rzp.io/i/qr_X.png",
        )
        order = self.plain_order("2500.00")

        collection_service.create_upi_collection(
            order=order, staff=self.staff, shift=self.shift,
        )
        order.refresh_from_db()

        self.assertEqual(order.channel, SalesChannel.POS)
        self.assertEqual(order.pos_shift_id, self.shift.id)

    def test_a_sale_is_never_moved_onto_a_second_shift(self):
        """Cash taken yesterday belongs to yesterday's drawer. Re-stamping would
        unbalance both shifts at once."""
        order = self.plain_order()
        services.take_cash_tender(
            order=order, shift=self.shift, staff=self.staff, amount_applied=Decimal("2000.00"),
        )
        services.close_shift(
            shift=self.shift, staff=self.staff, counted_cash=Decimal("4000"), force=True,
        )
        tomorrow = services.open_shift(terminal=self.terminal, staff=self.staff)

        services.attach_to_counter(order=order, shift=tomorrow, staff=self.staff)
        order.refresh_from_db()

        self.assertEqual(order.pos_shift_id, self.shift.id)


class ShiftSummaryTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.staff = User.objects.create_user(
            email="priya@aurorablings.com", password="x", first_name="P", last_name="S",
            role=UserRole.STAFF,
        )
        self.client.force_authenticate(self.staff)
        self.terminal = POSTerminal.objects.create(code="STALL-01", name="Stall")
        self.shift = services.open_shift(
            terminal=self.terminal, staff=self.staff, opening_float=Decimal("2000"),
        )

    def test_summary_separates_cash_from_gateway_takings(self):
        from apps.payments import tender_service
        from apps.payments.models import TenderMethod

        order = Order.objects.create(
            guest_email="w@example.com", status=OrderStatus.PLACED,
            payment_status=PaymentStatus.PENDING,
            subtotal=Decimal("4798.00"), grand_total=Decimal("4798.00"),
        )
        services.take_cash_tender(
            order=order, shift=self.shift, staff=self.staff, amount_applied=Decimal("2000.00"),
        )
        tender_service.record_tender(
            order=order, method=TenderMethod.UPI, amount_applied=Decimal("2798.00"),
            provider="razorpay", provider_ref="pay_SUMMARY01", shift=self.shift,
        )
        services.record_cash_movement(
            shift=self.shift, movement_type=CashMovementType.PAY_OUT,
            amount=Decimal("300.00"), reason="packing material", staff=self.staff,
        )

        summary = self.client.get(
            reverse("pos:shift-summary", kwargs={"shift_id": self.shift.id})
        ).data

        self.assertEqual(summary["orders"], 1)
        self.assertEqual(summary["by_tender"]["cash"]["total"], "2000.00")
        self.assertEqual(summary["by_tender"]["upi"]["total"], "2798.00")
        self.assertEqual(summary["cash_taken"], "2000.00")
        # Only cash and the pay-out move the drawer; the UPI leg does not.
        self.assertEqual(summary["expected_cash"], "3700.00")
        self.assertEqual(summary["part_paid_open"], 0)

    def test_shift_history_lists_newest_first(self):
        services.close_shift(shift=self.shift, staff=self.staff, counted_cash=Decimal("2000"))
        later = services.open_shift(terminal=self.terminal, staff=self.staff)

        rows = self.client.get(reverse("pos:shift-history")).data
        self.assertEqual(rows[0]["id"], str(later.id))
        self.assertEqual(len(rows), 2)
