"""
A counter sale is finished when it is paid.

The goods changed hands across the counter, so there is no shipment, no
courier, and nothing left to chase. The shared state machine routes every order
through PROCESSING → SHIPPED → DELIVERED before COMPLETED, which for a stall
sale means it sits at PAID for ever: permanently open in reporting, and sitting
in every queue that exists to find unfinished orders.

The narrowness is the point — carry-away only, from PAID only. An online order
must never be able to skip its shipment.
"""

from decimal import Decimal

from django.test import TestCase

from apps.accounts.models import User, UserRole
from apps.orders import services as order_services
from apps.orders.models import (
    FulfilmentType, FulfillmentMethod, Order, OrderStatus, PaymentStatus,
    ShippingApprovalStatus,
)


class CounterCompletionTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            email="priya@aurorablings.com", password="x", first_name="P", last_name="S",
            role=UserRole.STAFF,
        )

    def order(self, fulfilment=FulfilmentType.CARRY_AWAY, status=OrderStatus.PLACED):
        return Order.objects.create(
            guest_email="walkin@example.com",
            status=status, payment_status=PaymentStatus.PENDING,
            subtotal=Decimal("349.00"), grand_total=Decimal("349.00"),
            fulfilment_type=fulfilment,
        )

    def test_a_paid_counter_sale_closes_itself(self):
        order = order_services.mark_paid(
            order=self.order(), payment_reference="pay_1", changed_by=self.staff,
        )

        self.assertEqual(order.status, OrderStatus.COMPLETED)
        self.assertIsNotNone(order.delivered_at)

    def test_the_close_is_recorded_in_the_history(self):
        order = order_services.mark_paid(
            order=self.order(), payment_reference="pay_1", changed_by=self.staff,
        )

        last = order.status_history.order_by("-created_at").first()
        self.assertEqual(last.to_status, OrderStatus.COMPLETED)
        self.assertIn("counter", last.notes.lower())

    def test_a_ship_to_sale_stops_at_paid(self):
        """Nothing here may let an order with a shipment skip it."""
        order = order_services.mark_paid(
            order=self.order(fulfilment=FulfilmentType.SHIP),
            payment_reference="pay_1", changed_by=self.staff,
        )

        self.assertEqual(order.status, OrderStatus.PAID)

    def test_an_online_paid_order_cannot_jump_to_completed(self):
        order = self.order(fulfilment=FulfilmentType.SHIP, status=OrderStatus.PAID)

        self.assertFalse(order.can_transition_to(OrderStatus.COMPLETED))

    def test_a_counter_sale_cannot_jump_from_placed_to_completed(self):
        """Only from PAID. An unpaid sale is not a finished one."""
        order = self.order(status=OrderStatus.PLACED)

        self.assertFalse(order.can_transition_to(OrderStatus.COMPLETED))

    def test_the_new_choices_describe_a_handover(self):
        self.assertEqual(ShippingApprovalStatus.NOT_REQUIRED, "not_required")
        self.assertEqual(FulfillmentMethod.COUNTER, "counter")
