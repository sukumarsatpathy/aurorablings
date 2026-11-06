"""
Quick items: barcode-less pieces sold with a photo, never added to the catalogue.

What has to hold:
  * they are not Products — nothing reaches the website;
  * the price comes from the server, never the tablet;
  * the count goes down on a sale and back up on any cancellation, exactly once;
  * a sale without quick items is untouched by any of this.
"""

from decimal import Decimal
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image
from rest_framework.test import APIClient

from apps.accounts.models import User, UserRole
from apps.catalog.models import Category, Product, ProductVariant
from apps.inventory.models import Warehouse, WarehouseStock
from apps.orders.models import FulfilmentType, OrderItem, OrderStatus
from apps.payments import tender_service
from apps.pos import order_service, quick_items, services
from apps.pos.collection_service import payment_state
from apps.pos.models import POSQuickItem, POSQuickSaleLine, POSTerminal
from apps.surcharge.models import ShippingMethod, ShippingRule


def photo(name="piece.jpg"):
    buf = BytesIO()
    Image.new("RGB", (40, 30), (200, 150, 50)).save(buf, format="JPEG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/jpeg")


class QuickItemSaleTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="owner@aurorablings.com", password="x", first_name="O", last_name="W",
            role=UserRole.ADMIN,
        )
        self.terminal = POSTerminal.objects.create(code="SHOP-01", name="Shop")
        self.shift = services.open_shift(
            terminal=self.terminal, staff=self.admin, opening_float=Decimal("1000"),
        )
        self.warehouse = Warehouse.objects.create(
            name="Puri", code="puri", is_active=True, is_default=True,
        )
        category = Category.objects.create(name="Earrings", slug="earrings")
        product = Product.objects.create(
            name="Aurora Studs", slug="aurora-studs", category=category, is_active=True,
        )
        self.variant = ProductVariant.objects.create(
            product=product, sku="EAR-001", price=Decimal("349.00"),
            stock_quantity=0, is_active=True, is_default=True,
        )
        WarehouseStock.objects.create(
            variant=self.variant, warehouse=self.warehouse, on_hand=20, reserved=0, available=20,
        )
        self.item = quick_items.create_quick_item(
            name="Red stone jhumka", price="450", quantity=3, staff=self.admin,
        )

    def sell(self, lines, **kw):
        return order_service.create_pos_order(
            items=lines, shift=self.shift, staff=self.admin,
            fulfilment_type=FulfilmentType.CARRY_AWAY, **kw,
        )

    # ── the record ──────────────────────────────────────────

    def test_a_quick_item_is_not_a_catalogue_product(self):
        products_before = Product.all_objects.count()
        quick_items.create_quick_item(name="Anklet", price="120", quantity=2, image=photo())
        self.assertEqual(Product.all_objects.count(), products_before)

    def test_the_photo_is_stored_as_webp(self):
        item = quick_items.create_quick_item(name="Anklet", price="120", quantity=2, image=photo())
        self.assertTrue(item.image.name.endswith(".webp"))

    def test_price_and_name_are_required(self):
        with self.assertRaises(quick_items.QuickItemError):
            quick_items.create_quick_item(name="", price="100")
        with self.assertRaises(quick_items.QuickItemError):
            quick_items.create_quick_item(name="Ring", price="0")

    # ── selling ─────────────────────────────────────────────

    def test_a_quick_only_sale_is_priced_from_the_server_and_takes_stock(self):
        order = self.sell([{"quick_item_id": str(self.item.id), "quantity": 2}])

        self.assertEqual(order.status, OrderStatus.PLACED)
        self.assertEqual(order.subtotal, Decimal("900.00"))
        self.assertEqual(order.grand_total, Decimal("900.00"))
        line = order.items.get()
        self.assertIsNone(line.variant_id)
        self.assertEqual(line.product_name, "Red stone jhumka")
        self.assertEqual(line.unit_price, Decimal("450.00"))
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 1)
        self.assertEqual(order.pos_shift_id, self.shift.id)

    def test_a_mixed_sale_has_both_lines_and_one_total(self):
        order = self.sell([
            {"variant_id": str(self.variant.id), "quantity": 1},
            {"quick_item_id": str(self.item.id), "quantity": 1},
        ])
        self.assertEqual(order.items.count(), 2)
        self.assertEqual(order.subtotal, Decimal("799.00"))
        self.assertEqual(order.grand_total, Decimal("799.00"))

    def test_a_carried_away_quick_sale_pays_no_shipping(self):
        ShippingRule.objects.create(
            name="Standard", method=ShippingMethod.FREE_THRESHOLD,
            flat_rate=Decimal("100.00"), free_threshold_amount=Decimal("1000.00"),
            is_active=True,
        )
        order = self.sell([{"quick_item_id": str(self.item.id), "quantity": 1}])
        self.assertEqual(order.shipping_cost, Decimal("0.00"))
        self.assertEqual(order.grand_total, Decimal("450.00"))

    def test_the_quote_agrees_with_the_sale(self):
        lines = [
            {"variant_id": str(self.variant.id), "quantity": 2},
            {"quick_item_id": str(self.item.id), "quantity": 1},
        ]
        quoted = order_service.quote(items=lines, fulfilment_type=FulfilmentType.CARRY_AWAY)
        order = self.sell(lines)
        self.assertEqual(Decimal(quoted["grand_total"]), order.grand_total)

    def test_more_than_on_hand_is_refused_and_nothing_is_created(self):
        orders_before = OrderItem.objects.count()
        with self.assertRaises(order_service.POSOrderError):
            self.sell([{"quick_item_id": str(self.item.id), "quantity": 4}])
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 3)
        self.assertEqual(OrderItem.objects.count(), orders_before)

    def test_a_hidden_item_cannot_be_sold(self):
        quick_items.update_quick_item(item=self.item, is_active=False)
        with self.assertRaises(order_service.POSOrderError):
            self.sell([{"quick_item_id": str(self.item.id), "quantity": 1}])

    def test_a_later_price_change_does_not_touch_a_past_sale(self):
        order = self.sell([{"quick_item_id": str(self.item.id), "quantity": 1}])
        quick_items.update_quick_item(item=self.item, price="999")
        self.assertEqual(order.items.get().unit_price, Decimal("450.00"))

    # ── putting it back ─────────────────────────────────────

    def test_voiding_the_sale_puts_the_pieces_back_once(self):
        order = self.sell([{"quick_item_id": str(self.item.id), "quantity": 2}])
        services.void_sale(order=order, staff=self.admin, reason="customer left")
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 3)

        # A second save of the cancelled order must not add them again.
        order.refresh_from_db()
        order.save()
        quick_items.restock_order(order)
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 3)
        self.assertIsNotNone(POSQuickSaleLine.objects.get(order=order).restocked_at)

    def test_back_to_cart_gets_the_quick_lines(self):
        order = self.sell([
            {"variant_id": str(self.variant.id), "quantity": 1},
            {"quick_item_id": str(self.item.id), "quantity": 2},
        ])
        state = payment_state(order=order)
        self.assertEqual(state["items"], [{"variant_id": str(self.variant.id), "quantity": 1}])
        self.assertEqual(state["quick_items"], [{"quick_item_id": str(self.item.id), "quantity": 2}])

    def test_cash_payment_settles_a_quick_sale(self):
        order = self.sell([{"quick_item_id": str(self.item.id), "quantity": 1}])
        services.take_cash_tender(
            order=order, shift=self.shift, staff=self.admin,
            amount_applied=Decimal("450.00"), cash_received=Decimal("500.00"),
        )
        self.assertEqual(tender_service.balance_due(order), Decimal("0.00"))


class QuickItemApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="owner@aurorablings.com", password="x", first_name="O", last_name="W",
            role=UserRole.ADMIN,
        )
        self.customer = User.objects.create_user(
            email="c@example.com", password="x", first_name="C", last_name="C",
        )
        self.client = APIClient()

    def test_create_with_photo_and_search(self):
        self.client.force_authenticate(self.admin)
        res = self.client.post("/api/v1/pos/quick-items/", {
            "name": "Silver toe ring", "price": "199", "quantity": "5", "image": photo(),
        }, format="multipart")
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(res.data["quantity"], 5)
        self.assertTrue(res.data["image"])

        found = self.client.get("/api/v1/pos/quick-items/", {"q": "toe"}).data
        self.assertEqual([r["name"] for r in found], ["Silver toe ring"])

    def test_a_sold_out_item_is_left_out_of_search(self):
        POSQuickItem.objects.create(name="Gone", price=Decimal("10"), quantity=0)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get("/api/v1/pos/quick-items/").data, [])

    def test_a_line_must_name_exactly_one_thing(self):
        self.client.force_authenticate(self.admin)
        res = self.client.post("/api/v1/pos/quote/", {"items": [{"quantity": 1}]}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_customers_cannot_create_quick_items(self):
        self.client.force_authenticate(self.customer)
        res = self.client.post("/api/v1/pos/quick-items/", {"name": "x", "price": "1"})
        self.assertEqual(res.status_code, 403)
