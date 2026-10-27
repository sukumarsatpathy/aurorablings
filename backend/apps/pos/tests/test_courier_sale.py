"""
Counter sales that leave by courier.

What must hold:
  - a courier sale needs a complete delivery address; a hand-over sale needs none
  - the label's name/phone become the customer's when staff didn't type them
  - once paid and linked to a customer, the address lands in their address book
  - it never replaces an address book default the customer already has
  - a hand-over sale writes nothing to the address book
"""

from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from apps.accounts import customer_linking
from apps.accounts.models import Address, User, UserRole
from apps.orders.models import FulfilmentType, Order, OrderStatus, PaymentStatus
from apps.pos import order_service, services
from apps.pos.models import POSTerminal

ADDRESS = {
    "full_name": "Asha Rao",
    "phone": "98765 43210",
    "line1": "12 Temple Road",
    "line2": "Near Gandharbha Matha",
    "city": "Puri",
    "state": "Odisha",
    "pincode": "752002",
}


class CourierAddressValidationTests(TestCase):
    def test_complete_address_is_cleaned(self):
        cleaned = order_service.clean_courier_address(ADDRESS)
        self.assertEqual(cleaned["phone"], "9876543210")
        self.assertEqual(cleaned["pincode"], "752002")
        self.assertEqual(cleaned["postal_code"], "752002")
        self.assertEqual(cleaned["address_line1"], "12 Temple Road")
        self.assertEqual(cleaned["country"], "India")

    def test_missing_parts_are_named(self):
        with self.assertRaises(order_service.POSOrderError) as ctx:
            order_service.clean_courier_address({**ADDRESS, "city": "", "pincode": "7520"})
        message = str(ctx.exception)
        self.assertIn("city", message)
        self.assertIn("6-digit pincode", message)

    def test_state_code_is_kept_and_counts_as_state(self):
        cleaned = order_service.clean_courier_address({**ADDRESS, "state": "", "state_code": "OD"})
        self.assertEqual(cleaned["state_code"], "OD")

    def test_no_address_is_refused(self):
        with self.assertRaises(order_service.POSOrderError):
            order_service.clean_courier_address(None)


class CourierSaleCreationTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            email="priya@aurorablings.com", password="x", first_name="P", last_name="S",
            role=UserRole.STAFF,
        )
        self.terminal = POSTerminal.objects.create(code="SHOP-01", name="Shop")
        self.shift = services.open_shift(terminal=self.terminal, staff=self.staff)

    def _create(self, **kwargs):
        placed = Order.objects.create(
            status=OrderStatus.PLACED, payment_status=PaymentStatus.PENDING,
            subtotal=Decimal("999.00"), grand_total=Decimal("1059.00"), shipping_cost=Decimal("60.00"),
        )

        def fake_create(**create_kwargs):
            placed.shipping_address = create_kwargs.get("shipping_address") or {}
            placed.save(update_fields=["shipping_address"])
            return placed

        with patch.object(order_service.order_services, "create_admin_order_from_items", side_effect=fake_create):
            return order_service.create_pos_order(
                items=[{"variant_id": "x", "quantity": 1}], shift=self.shift, staff=self.staff, **kwargs,
            )

    def test_courier_sale_keeps_address_and_shipping(self):
        order = self._create(fulfilment_type=FulfilmentType.SHIP, shipping_address=ADDRESS)
        order.refresh_from_db()
        self.assertEqual(order.fulfilment_type, FulfilmentType.SHIP)
        self.assertEqual(order.shipping_address["pincode"], "752002")
        self.assertEqual(order.shipping_cost, Decimal("60.00"))
        # Staff typed no customer — the label's details stand in.
        self.assertEqual(order.contact_name, "Asha Rao")
        self.assertEqual(order.contact_phone, "9876543210")

    def test_typed_customer_wins_over_label(self):
        order = self._create(
            fulfilment_type=FulfilmentType.SHIP, shipping_address=ADDRESS,
            contact_name="Ravi Rao", contact_phone="9000000001",
        )
        order.refresh_from_db()
        self.assertEqual(order.contact_name, "Ravi Rao")
        self.assertEqual(order.contact_phone, "9000000001")

    def test_courier_sale_without_address_is_refused(self):
        with self.assertRaises(order_service.POSOrderError):
            self._create(fulfilment_type=FulfilmentType.SHIP, shipping_address={})

    def test_hand_over_needs_no_address_and_drops_shipping(self):
        order = self._create(fulfilment_type=FulfilmentType.CARRY_AWAY)
        order.refresh_from_db()
        self.assertEqual(order.fulfilment_type, FulfilmentType.CARRY_AWAY)
        self.assertEqual(order.shipping_cost, Decimal("0.00"))
        self.assertEqual(order.grand_total, Decimal("999.00"))


class AddressBookTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            email="asha@example.com", password="x", first_name="Asha", last_name="Rao",
            phone="9876543210",
        )

    def _paid_order(self, fulfilment=FulfilmentType.SHIP, address=ADDRESS):
        return Order.objects.create(
            status=OrderStatus.PAID, payment_status=PaymentStatus.PAID,
            subtotal=Decimal("999.00"), grand_total=Decimal("999.00"),
            fulfilment_type=fulfilment, shipping_address=dict(address or {}),
            contact_name="Asha Rao", contact_phone="9876543210", guest_email="asha@example.com",
        )

    def test_linking_an_existing_customer_saves_the_address(self):
        customer_linking.link_or_create_customer(
            order=self._paid_order(), name="Asha Rao", phone="9876543210", email="asha@example.com",
        )
        address = Address.objects.get(user=self.customer)
        self.assertEqual(address.line1, "12 Temple Road")
        self.assertEqual(address.postal_code, "752002")
        self.assertTrue(address.is_default)

    def test_new_account_gets_the_address(self):
        order = self._paid_order()
        order.contact_phone = "9111111111"
        order.guest_email = "new@example.com"
        order.save()
        result = customer_linking.link_or_create_customer(
            order=order, name="New Person", phone="9111111111", email="new@example.com",
        )
        self.assertTrue(result.created)
        self.assertEqual(Address.objects.filter(user=result.user).count(), 1)

    def test_existing_default_is_not_replaced(self):
        Address.objects.create(
            user=self.customer, address_type="shipping", is_default=True,
            full_name="Asha Rao", line1="1 Home Street", city="Bhubaneswar", postal_code="751001",
        )
        customer_linking.link_or_create_customer(
            order=self._paid_order(), name="Asha Rao", phone="9876543210", email="asha@example.com",
        )
        addresses = Address.objects.filter(user=self.customer)
        self.assertEqual(addresses.count(), 2)
        self.assertEqual(addresses.get(is_default=True).line1, "1 Home Street")

    def test_same_address_is_not_duplicated(self):
        for _ in range(2):
            customer_linking.link_or_create_customer(
                order=self._paid_order(), name="Asha Rao", phone="9876543210", email="asha@example.com",
            )
        self.assertEqual(Address.objects.filter(user=self.customer).count(), 1)

    def test_hand_over_sale_saves_nothing(self):
        customer_linking.link_or_create_customer(
            order=self._paid_order(fulfilment=FulfilmentType.CARRY_AWAY),
            name="Asha Rao", phone="9876543210", email="asha@example.com",
        )
        self.assertFalse(Address.objects.filter(user=self.customer).exists())

    def test_incomplete_address_is_skipped(self):
        saved = customer_linking.save_address_to_profile(
            user=self.customer, address={"full_name": "Asha", "city": "Puri"},
        )
        self.assertIsNone(saved)
        self.assertFalse(Address.objects.filter(user=self.customer).exists())
