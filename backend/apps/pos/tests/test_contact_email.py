"""
The email stays on the order even when no account is wanted.

These are two different questions and they were being answered by one field.
The till only sent the address if the account box was ticked, so an email taken
purely so a receipt could be sent was thrown away — leaving a paid sale with no
way to reach the customer, and no record that an address was ever given.

The receipt is transactional; the account is a choice. Kept apart here.
"""

from decimal import Decimal

from django.test import TestCase

from apps.accounts.models import User, UserRole
from apps.catalog.models import Category, Product, ProductVariant
from apps.inventory.models import Warehouse, WarehouseStock
from apps.orders.models import FulfilmentType
from apps.pos import order_service, services
from apps.pos.models import POSTerminal


class ContactEmailTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            email="priya@aurorablings.com", password="x", first_name="P", last_name="S",
            role=UserRole.STAFF,
        )
        self.terminal = POSTerminal.objects.create(code="STALL-01", name="Stall")
        self.shift = services.open_shift(
            terminal=self.terminal, staff=self.staff, opening_float=Decimal("2000"),
        )
        category = Category.objects.create(name="Earrings", slug="earrings")
        product = Product.objects.create(
            name="Aurora Studs", slug="aurora-studs", category=category, is_active=True,
        )
        self.variant = ProductVariant.objects.create(
            product=product, sku="EAR-001", price=Decimal("349.00"),
            stock_quantity=0, is_active=True, is_default=True,
        )
        warehouse = Warehouse.objects.create(
            name="Bhubaneswar", code="bbsr", is_active=True, is_default=True,
        )
        WarehouseStock.objects.create(
            variant=self.variant, warehouse=warehouse, on_hand=20, reserved=0, available=20,
        )

    def sale(self, **kwargs):
        return order_service.create_pos_order(
            items=[{"variant_id": str(self.variant.id), "quantity": 1}],
            shift=self.shift, staff=self.staff,
            fulfilment_type=FulfilmentType.CARRY_AWAY,
            **kwargs,
        )

    def test_the_email_is_kept_when_no_account_is_wanted(self):
        order = self.sale(
            contact_name="Anita S", contact_phone="9876543210",
            contact_email="anita@example.com", create_account=False,
        )

        self.assertEqual(order.guest_email, "anita@example.com")
        self.assertFalse(order.contact_wants_account)

    def test_an_account_is_wanted_when_asked_for(self):
        order = self.sale(
            contact_name="Anita S", contact_phone="9876543210",
            contact_email="anita@example.com", create_account=True,
        )

        self.assertEqual(order.guest_email, "anita@example.com")
        self.assertTrue(order.contact_wants_account)

    def test_no_email_means_no_account_whatever_was_ticked(self):
        """The box can be left ticked by default; without an address it means nothing."""
        order = self.sale(
            contact_name="Anita S", contact_phone="9876543210", create_account=True,
        )

        self.assertEqual(order.guest_email, "")
        self.assertFalse(order.contact_wants_account)

    def test_the_settlement_task_does_not_create_an_account_when_declined(self):
        from apps.accounts import customer_linking

        order = self.sale(
            contact_name="Anita S", contact_phone="9876543210",
            contact_email="anita@example.com", create_account=False,
        )

        result = customer_linking.link_or_create_customer(
            order=order, name=order.contact_name, phone=order.contact_phone,
            email=order.guest_email, create_account=order.contact_wants_account,
        )

        self.assertFalse(result.created)
        self.assertFalse(User.objects.filter(email="anita@example.com").exists())
        order.refresh_from_db()
        self.assertIsNone(order.user_id)
        # But the address is still there, so the receipt can be sent.
        self.assertEqual(order.guest_email, "anita@example.com")
