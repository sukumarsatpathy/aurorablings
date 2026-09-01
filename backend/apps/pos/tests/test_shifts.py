"""
Shift arithmetic and the cash tender.

The question every one of these asks is the same: at the end of the day, does the
number the system expects in the drawer match the notes actually in the drawer,
and if it doesn't, can you tell why?
"""

from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.accounts.models import User, UserRole
from apps.orders.models import Order, OrderStatus, PaymentStatus
from apps.payments import tender_service as ledger
from apps.payments.models import TenderMethod
from apps.pos import services
from apps.pos.models import CashMovementType, POSShift, POSTerminal, ShiftStatus


class ShiftTestCase(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            email="priya@aurorablings.com", password="x", first_name="Priya", last_name="S",
            role=UserRole.STAFF,
        )
        self.terminal = POSTerminal.objects.create(code="STALL-01", name="Bhubaneswar stall")

    def order(self, total="4798.00", shift=None):
        return Order.objects.create(
            guest_email="walkin@example.com",
            status=OrderStatus.PLACED,
            payment_status=PaymentStatus.PENDING,
            subtotal=Decimal(total),
            grand_total=Decimal(total),
            currency="INR",
            pos_shift=shift,
            pos_terminal=self.terminal if shift else None,
        )


class ShiftLifecycleTests(ShiftTestCase):

    def test_one_open_shift_per_terminal(self):
        """Two open shifts on one terminal means two people counting the same
        drawer. Refused in the service, and again by the database."""
        services.open_shift(terminal=self.terminal, staff=self.staff, opening_float=Decimal("2000"))

        with self.assertRaises(services.ShiftError):
            services.open_shift(terminal=self.terminal, staff=self.staff)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                POSShift.objects.create(
                    terminal=self.terminal, opened_by=self.staff, status=ShiftStatus.OPEN,
                )

    def test_expected_cash_is_float_plus_cash_sales(self):
        shift = services.open_shift(terminal=self.terminal, staff=self.staff, opening_float=Decimal("2000"))
        order = self.order("1850.00", shift=shift)

        services.take_cash_tender(
            order=order, shift=shift, staff=self.staff,
            amount_applied=Decimal("1850.00"), cash_received=Decimal("2000.00"),
        )

        # Change went back to the customer, so only the applied amount stays.
        self.assertEqual(services.cash_taken(shift), Decimal("1850.00"))
        self.assertEqual(services.expected_cash(shift), Decimal("3850.00"))

    def test_upi_sales_do_not_touch_the_drawer(self):
        """The split sale's whole point: cash reconciles against cash, the
        gateway settlement against gateway legs, and neither counts the other."""
        shift = services.open_shift(terminal=self.terminal, staff=self.staff, opening_float=Decimal("2000"))
        order = self.order("4798.00", shift=shift)

        services.take_cash_tender(
            order=order, shift=shift, staff=self.staff, amount_applied=Decimal("2000.00"),
        )
        ledger.record_tender(
            order=order, method=TenderMethod.UPI, amount_applied=Decimal("2798.00"),
            provider="razorpay", provider_ref="pay_SPLITSHIFT01", shift=shift,
        )
        order.refresh_from_db()

        self.assertEqual(order.payment_status, PaymentStatus.PAID)
        self.assertEqual(services.cash_taken(shift), Decimal("2000.00"))
        self.assertEqual(services.expected_cash(shift), Decimal("4000.00"))

    def test_pay_out_reduces_expected_cash(self):
        shift = services.open_shift(terminal=self.terminal, staff=self.staff, opening_float=Decimal("2000"))
        services.record_cash_movement(
            shift=shift, movement_type=CashMovementType.PAY_OUT,
            amount=Decimal("500.00"), reason="tea and packing material", staff=self.staff,
        )
        self.assertEqual(services.expected_cash(shift), Decimal("1500.00"))

    def test_cash_movement_requires_a_reason(self):
        shift = services.open_shift(terminal=self.terminal, staff=self.staff)
        with self.assertRaises(services.ShiftError):
            services.record_cash_movement(
                shift=shift, movement_type=CashMovementType.PAY_OUT,
                amount=Decimal("500.00"), reason="", staff=self.staff,
            )

    def test_close_records_variance_when_the_count_is_short(self):
        shift = services.open_shift(terminal=self.terminal, staff=self.staff, opening_float=Decimal("2000"))
        order = self.order("1850.00", shift=shift)
        services.take_cash_tender(
            order=order, shift=shift, staff=self.staff, amount_applied=Decimal("1850.00"),
        )

        closed = services.close_shift(
            shift=shift, staff=self.staff, counted_cash=Decimal("3750.00"), note="one note missing",
        )

        self.assertEqual(closed.expected_cash, Decimal("3850.00"))
        self.assertEqual(closed.counted_cash, Decimal("3750.00"))
        self.assertEqual(closed.variance, Decimal("-100.00"))
        self.assertEqual(closed.status, ShiftStatus.CLOSED)

    def test_close_refuses_while_a_part_paid_sale_holds_cash(self):
        """The exact scenario: cash taken, customer walked off before the QR was
        paid, and the shift is about to be closed as if nothing happened."""
        shift = services.open_shift(terminal=self.terminal, staff=self.staff, opening_float=Decimal("2000"))
        order = self.order("4798.00", shift=shift)
        services.take_cash_tender(
            order=order, shift=shift, staff=self.staff, amount_applied=Decimal("2000.00"),
        )
        order.refresh_from_db()
        self.assertEqual(order.payment_status, PaymentStatus.PARTIALLY_PAID)

        with self.assertRaises(services.ShiftError):
            services.close_shift(shift=shift, staff=self.staff, counted_cash=Decimal("4000.00"))

        # A stall still has to be able to pack up — but it goes on the record.
        closed = services.close_shift(
            shift=shift, staff=self.staff, counted_cash=Decimal("4000.00"), force=True,
        )
        self.assertEqual(closed.status, ShiftStatus.CLOSED)
        self.assertIn("part-paid", closed.close_note)

    def test_voiding_a_cash_leg_lowers_expected_cash_exactly_once(self):
        """Voiding must not be double-counted: the tender leaves cash_taken, and
        no compensating movement row is written."""
        shift = services.open_shift(terminal=self.terminal, staff=self.staff, opening_float=Decimal("2000"))
        order = self.order("4798.00", shift=shift)
        tender = services.take_cash_tender(
            order=order, shift=shift, staff=self.staff, amount_applied=Decimal("2000.00"),
        )
        self.assertEqual(services.expected_cash(shift), Decimal("4000.00"))

        services.void_cash_tender(tender=tender, staff=self.staff, reason="customer left")
        order.refresh_from_db()

        self.assertEqual(services.expected_cash(shift), Decimal("2000.00"))
        self.assertEqual(order.payment_status, PaymentStatus.PENDING)
        self.assertEqual(shift.cash_movements.count(), 0)

    def test_cannot_take_cash_against_a_closed_shift(self):
        shift = services.open_shift(terminal=self.terminal, staff=self.staff)
        services.close_shift(shift=shift, staff=self.staff, counted_cash=Decimal("0"))
        order = self.order("500.00", shift=shift)

        with self.assertRaises(services.ShiftError):
            services.take_cash_tender(
                order=order, shift=shift, staff=self.staff, amount_applied=Decimal("500.00"),
            )
