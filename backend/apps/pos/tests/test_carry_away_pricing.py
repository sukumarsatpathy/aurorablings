"""
A carried-away sale is not a delivery.

The surcharge engine prices every order as one, because until the POS existed
every order was one. Its free-above-threshold shipping rule therefore lands a
flat rate on a counter sale under the threshold — which at a stall is most of
them — and the customer is standing there watching the screen while it happens.

These tests pin the split: shipping goes for carry-away, and stays for ship-to.
"""

from decimal import Decimal

from django.test import TestCase

from apps.accounts.models import User, UserRole
from apps.catalog.models import Category, Product, ProductVariant
from apps.inventory.models import Warehouse, WarehouseStock
from apps.orders.models import FulfilmentType
from apps.pos import order_service, services
from apps.pos.models import POSTerminal
from apps.surcharge.models import ShippingMethod, ShippingRule


class CarryAwayPricingTests(TestCase):
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

        # ₹100 below ₹1,000 — the shape that produced the phantom charge.
        ShippingRule.objects.create(
            name="Standard", method=ShippingMethod.FREE_THRESHOLD,
            flat_rate=Decimal("100.00"), free_threshold_amount=Decimal("1000.00"),
            is_active=True,
        )

    def items(self, quantity=1):
        return [{"variant_id": str(self.variant.id), "quantity": quantity}]

    def test_a_carried_away_sale_is_not_charged_shipping(self):
        order = order_service.create_pos_order(
            items=self.items(), shift=self.shift, staff=self.staff,
            fulfilment_type=FulfilmentType.CARRY_AWAY,
        )

        self.assertEqual(order.shipping_cost, Decimal("0.00"))
        self.assertEqual(order.grand_total, order.subtotal - order.discount_amount + order.tax_amount)

    def test_a_ship_to_sale_still_pays_it(self):
        """The charge is correct when something is actually being posted."""
        order = order_service.create_pos_order(
            items=self.items(), shift=self.shift, staff=self.staff,
            fulfilment_type=FulfilmentType.SHIP,
            shipping_address={"line1": "1 Janpath", "city": "Bhubaneswar",
                              "state_code": "OD", "pincode": "751001"},
        )

        self.assertEqual(order.shipping_cost, Decimal("100.00"))

    def test_the_quote_agrees_with_the_sale_it_becomes(self):
        """Staff read the quote out loud before the order exists."""
        quoted = order_service.quote(
            items=self.items(), fulfilment_type=FulfilmentType.CARRY_AWAY,
        )
        order = order_service.create_pos_order(
            items=self.items(), shift=self.shift, staff=self.staff,
            fulfilment_type=FulfilmentType.CARRY_AWAY,
        )

        self.assertEqual(Decimal(str(quoted["grand_total"])), order.grand_total)
