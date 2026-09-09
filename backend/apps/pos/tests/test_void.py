"""
Voiding a sale that already holds money, and the sweeper that must not.

The failure this guards against is silent: a background task cancels a counter
sale, releases the stock, marks it failed — and the Rs 2,000 in the drawer now
belongs to nothing.
"""

from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User, UserRole
from apps.orders.models import Order, OrderStatus, PaymentStatus, SalesChannel
from apps.payments import tender_service as ledger
from apps.payments.models import PaymentTransaction, TenderMethod, TenderStatus, TransactionStatus
from apps.pos import services
from apps.pos.models import POSTerminal


class VoidSaleTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            email="priya@aurorablings.com", password="x", first_name="P", last_name="S",
            role=UserRole.STAFF,
        )
        self.terminal = POSTerminal.objects.create(code="STALL-01", name="Stall")
        self.shift = services.open_shift(
            terminal=self.terminal, staff=self.staff, opening_float=Decimal("2000"),
        )

    def pos_order(self, total="4798.00"):
        return Order.objects.create(
            guest_email="walkin@example.com",
            status=OrderStatus.PLACED, payment_status=PaymentStatus.PENDING,
            subtotal=Decimal(total), grand_total=Decimal(total),
            channel=SalesChannel.POS, pos_shift=self.shift, pos_terminal=self.terminal,
        )

    def test_void_returns_the_cash_and_cancels_the_order(self):
        order = self.pos_order()
        services.take_cash_tender(
            order=order, shift=self.shift, staff=self.staff, amount_applied=Decimal("2000.00"),
        )
        self.assertEqual(services.expected_cash(self.shift), Decimal("4000.00"))

        services.void_sale(order=order, staff=self.staff, reason="customer changed their mind")
        order.refresh_from_db()

        self.assertEqual(order.status, OrderStatus.CANCELLED)
        self.assertEqual(services.expected_cash(self.shift), Decimal("2000.00"))
        self.assertEqual(order.tenders.filter(status=TenderStatus.CAPTURED).count(), 0)

    def test_void_refuses_when_a_gateway_leg_has_settled(self):
        """Money with Razorpay comes back through the refund API. Voiding the row
        would leave the customer's bank statement and our ledger disagreeing."""
        order = self.pos_order("2500.00")
        ledger.record_tender(
            order=order, method=TenderMethod.UPI, amount_applied=Decimal("2500.00"),
            provider="razorpay", provider_ref="pay_VOIDGUARD01", shift=self.shift,
        )

        with self.assertRaises(services.ShiftError) as ctx:
            services.void_sale(order=order, staff=self.staff, reason="mistake")
        self.assertIn("refund", str(ctx.exception).lower())

        order.refresh_from_db()
        self.assertEqual(order.payment_status, PaymentStatus.PAID)

    def test_void_needs_a_reason(self):
        order = self.pos_order()
        services.take_cash_tender(
            order=order, shift=self.shift, staff=self.staff, amount_applied=Decimal("2000.00"),
        )
        with self.assertRaises(services.ShiftError):
            services.void_sale(order=order, staff=self.staff, reason="")

    def test_part_paid_list_surfaces_the_sale(self):
        order = self.pos_order()
        services.take_cash_tender(
            order=order, shift=self.shift, staff=self.staff, amount_applied=Decimal("2000.00"),
        )
        listed = list(services.part_paid_orders(shift=self.shift))
        self.assertEqual([o.id for o in listed], [order.id])


class StaleSweeperTests(TestCase):
    """
    The sweeper cancels abandoned online checkouts. A part-paid counter sale looks
    identical to it from the transaction table — and must be left alone.
    """

    def setUp(self):
        self.staff = User.objects.create_user(
            email="priya@aurorablings.com", password="x", first_name="P", last_name="S",
            role=UserRole.STAFF,
        )
        self.terminal = POSTerminal.objects.create(code="STALL-01", name="Stall")
        self.shift = services.open_shift(terminal=self.terminal, staff=self.staff)

    def _stale_txn(self, order):
        txn = PaymentTransaction.objects.create(
            order=order, provider="razorpay", status=TransactionStatus.PENDING,
            amount=order.grand_total, total_amount=order.grand_total, currency="INR",
        )
        # Backdate past the timeout; created_at is auto_now_add.
        PaymentTransaction.objects.filter(pk=txn.pk).update(
            created_at=timezone.now() - timezone.timedelta(hours=3)
        )
        return txn

    def test_a_part_paid_counter_sale_is_not_swept(self):
        from apps.payments.tasks import expire_stale_razorpay_orders_task

        order = Order.objects.create(
            guest_email="walkin@example.com",
            status=OrderStatus.PLACED, payment_status=PaymentStatus.PENDING,
            subtotal=Decimal("4798.00"), grand_total=Decimal("4798.00"),
            channel=SalesChannel.POS, pos_shift=self.shift, pos_terminal=self.terminal,
        )
        services.take_cash_tender(
            order=order, shift=self.shift, staff=self.staff, amount_applied=Decimal("2000.00"),
        )
        self._stale_txn(order)

        expire_stale_razorpay_orders_task()
        order.refresh_from_db()

        self.assertEqual(order.status, OrderStatus.PLACED, "the sale was cancelled with cash against it")
        self.assertEqual(order.payment_status, PaymentStatus.PARTIALLY_PAID)
        self.assertEqual(services.expected_cash(self.shift), Decimal("2000.00"))

    @patch("apps.payments.services.reconcile_transaction_status", side_effect=lambda transaction: transaction)
    def test_a_genuinely_abandoned_checkout_is_still_swept(self, _mock):
        """The guard must not blunt the sweeper for the case it exists for."""
        from apps.payments.tasks import expire_stale_razorpay_orders_task

        order = Order.objects.create(
            guest_email="shopper@example.com",
            status=OrderStatus.PLACED, payment_status=PaymentStatus.PENDING,
            subtotal=Decimal("999.00"), grand_total=Decimal("999.00"),
        )
        self._stale_txn(order)

        expire_stale_razorpay_orders_task()
        order.refresh_from_db()

        self.assertEqual(order.status, OrderStatus.CANCELLED)
