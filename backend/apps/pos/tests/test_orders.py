"""
Ringing up a sale, and the discount controls.

The discount tests are the ones that matter: this is the margin leak a POS has to
be able to explain later, and every control has to hold when the request does not
come from our own UI.
"""

from decimal import Decimal

from django.test import TestCase, override_settings

from apps.accounts.models import User, UserRole
from apps.orders.models import (
    FulfilmentType, Order, OrderStatus, PaymentStatus, ShippingApprovalStatus,
)
from apps.payments import tender_service
from apps.payments.models import TenderMethod
from apps.pos import order_service, services
from apps.pos.models import POSTerminal


class DiscountControlTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            email="priya@aurorablings.com", password="x", first_name="P", last_name="S",
            role=UserRole.STAFF,
        )
        self.manager = User.objects.create_user(
            email="boss@aurorablings.com", password="managerpass123", first_name="B", last_name="S",
            role=UserRole.ADMIN,
        )
        self.terminal = POSTerminal.objects.create(code="STALL-01", name="Stall")
        self.shift = services.open_shift(terminal=self.terminal, staff=self.staff)

    def order(self, subtotal="4000.00"):
        return Order.objects.create(
            guest_email="w@example.com", status=OrderStatus.PLACED,
            payment_status=PaymentStatus.PENDING,
            subtotal=Decimal(subtotal), grand_total=Decimal(subtotal),
        )

    def test_a_discount_within_the_ceiling_needs_no_approval(self):
        order = self.order()
        order_service.apply_manual_discount(
            order=order, percent=Decimal("10"), reason="display_piece", staff=self.staff,
        )
        order.refresh_from_db()

        self.assertEqual(order.manual_discount_amount, Decimal("400.00"))
        self.assertEqual(order.grand_total, Decimal("3600.00"))
        self.assertIsNone(order.manual_discount_approved_by_id)

    def test_over_the_ceiling_is_refused_without_a_manager(self):
        """The tablet is supposed to ask for approval. This is what happens when
        the request doesn't come from the tablet."""
        order = self.order()
        with self.assertRaises(order_service.POSOrderError) as ctx:
            order_service.apply_manual_discount(
                order=order, percent=Decimal("25"), reason="bulk_purchase", staff=self.staff,
            )
        self.assertIn("manager", str(ctx.exception).lower())

        order.refresh_from_db()
        self.assertEqual(order.grand_total, Decimal("4000.00"))

    def test_over_the_ceiling_succeeds_with_a_manager_and_records_who(self):
        order = self.order()
        order_service.apply_manual_discount(
            order=order, percent=Decimal("25"), reason="bulk_purchase",
            staff=self.staff, approved_by=self.manager,
        )
        order.refresh_from_db()

        self.assertEqual(order.manual_discount_amount, Decimal("1000.00"))
        self.assertEqual(order.grand_total, Decimal("3000.00"))
        self.assertEqual(order.manual_discount_approved_by_id, self.manager.id)

    def test_a_flat_amount_is_measured_against_the_ceiling_too(self):
        """25% expressed in rupees is still 25%."""
        order = self.order()
        with self.assertRaises(order_service.POSOrderError):
            order_service.apply_manual_discount(
                order=order, amount=Decimal("1000.00"), reason="price_match", staff=self.staff,
            )

    def test_reason_must_come_from_the_fixed_list(self):
        order = self.order()
        with self.assertRaises(order_service.POSOrderError):
            order_service.apply_manual_discount(
                order=order, percent=Decimal("5"), reason="because she asked nicely",
                staff=self.staff,
            )

    def test_cannot_discount_a_sale_that_already_holds_money(self):
        """Changing the total under a settled tender leaves the ledger right and
        the order wrong."""
        order = self.order()
        tender_service.record_tender(
            order=order, method=TenderMethod.CASH, amount_applied=Decimal("1000.00"),
        )
        with self.assertRaises(order_service.POSOrderError) as ctx:
            order_service.apply_manual_discount(
                order=order, percent=Decimal("5"), reason="display_piece", staff=self.staff,
            )
        self.assertIn("void", str(ctx.exception).lower())

    def test_replacing_a_discount_does_not_compound_it(self):
        order = self.order()
        order_service.apply_manual_discount(
            order=order, percent=Decimal("10"), reason="display_piece", staff=self.staff,
        )
        order_service.apply_manual_discount(
            order=order, percent=Decimal("5"), reason="minor_defect", staff=self.staff,
        )
        order.refresh_from_db()

        self.assertEqual(order.manual_discount_amount, Decimal("200.00"))
        self.assertEqual(order.grand_total, Decimal("3800.00"))

    @override_settings(POS_DISCOUNT_CEILING_PCT=Decimal("20"))
    def test_the_ceiling_is_configurable(self):
        order = self.order()
        order_service.apply_manual_discount(
            order=order, percent=Decimal("15"), reason="repeat_customer", staff=self.staff,
        )
        order.refresh_from_db()
        self.assertEqual(order.manual_discount_amount, Decimal("600.00"))

    def test_only_an_admin_can_approve(self):
        """A staff member approving their own override is not a control."""
        self.assertIsNone(order_service.authenticate_approver(
            email=self.staff.email, password="x",
        ))
        self.assertEqual(
            order_service.authenticate_approver(
                email=self.manager.email, password="managerpass123",
            ),
            self.manager,
        )

    def test_a_wrong_manager_password_does_not_approve(self):
        self.assertIsNone(order_service.authenticate_approver(
            email=self.manager.email, password="not-the-password",
        ))


class CarryAwayFulfilmentTests(TestCase):
    """
    fulfilment_type existed as a field that nothing read. A carried-away stall
    sale could still be pushed into the courier pipeline.
    """

    def setUp(self):
        self.staff = User.objects.create_user(
            email="priya@aurorablings.com", password="x", first_name="P", last_name="S",
            role=UserRole.STAFF,
        )

    def carry_away_order(self):
        return Order.objects.create(
            guest_email="w@example.com", status=OrderStatus.PAID,
            payment_status=PaymentStatus.PAID,
            subtotal=Decimal("999.00"), grand_total=Decimal("999.00"),
            fulfilment_type=FulfilmentType.CARRY_AWAY,
        )

    def test_shipping_approval_refuses_a_carried_away_sale(self):
        from core.exceptions import ValidationError
        from apps.shipping.services import approve_order_shipping

        order = self.carry_away_order()
        with self.assertRaises(ValidationError) as ctx:
            approve_order_shipping(
                order_id=str(order.id), fulfillment_method="nimbuspost", approved_by=self.staff,
            )
        self.assertIn("carried away", str(ctx.exception).lower())

    def test_preflight_refuses_a_carried_away_sale(self):
        from apps.shipping.services import preflight_validate_order

        order = self.carry_away_order()
        order.shipping_approval_status = ShippingApprovalStatus.APPROVED
        order.save(update_fields=["shipping_approval_status"])

        result = preflight_validate_order(order)
        self.assertTrue(any("carried away" in e.lower() for e in result.errors))
