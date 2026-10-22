"""
Bulk Receive: a whole delivery in one save.

What matters: every line lands with its own ledger entry and the shared
reference; it's all-or-nothing (one bad line saves nothing); repeated
variants are added together; deleted products and inactive warehouses are
refused; the catalog the page loads has options, swatches and current stock,
hides deleted products, keeps drafts, and doesn't get slower per product.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APITestCase

from apps.catalog import services as catalog_services
from apps.catalog.models import Attribute, AttributeValue, Category, Product, ProductVariant
from apps.inventory import services
from apps.inventory.models import StockLedger, Warehouse, WarehouseStock

User = get_user_model()
URL = "/api/v1/inventory/stock/bulk-receive/"
CATALOG_URL = "/api/v1/inventory/stock/bulk-receive/catalog/"


class BulkReceiveTests(APITestCase):
    def setUp(self):
        admin = User.objects.create_user(
            email="a-bulk@example.com", password="pw123456", role="admin", is_staff=True, is_superuser=True,
        )
        self.client.force_authenticate(user=admin)
        self.puri = Warehouse.objects.create(name="Puri", code="puri-wrhs", is_default=True)
        self.closed = Warehouse.objects.create(name="Old", code="old", is_active=False)
        self.category = Category.objects.create(name="Bangles", slug="bangles")

        self.stack = Product.objects.create(name="Marble Stack", slug="marble-stack", category=self.category, is_active=True)
        colour = Attribute.objects.create(product=self.stack, name="Color", show_swatches=True)
        size = Attribute.objects.create(product=self.stack, name="Size")
        self.violet = AttributeValue.objects.create(attribute=colour, value="Violet", hex_code="#7F3FBF")
        self.rust = AttributeValue.objects.create(attribute=colour, value="Rust", hex_code="#B7410E")
        self.s24 = AttributeValue.objects.create(attribute=size, value="2-4")
        self.s26 = AttributeValue.objects.create(attribute=size, value="2-6")
        self.v = {}
        for c in (self.violet, self.rust):
            for s in (self.s24, self.s26):
                variant = ProductVariant.objects.create(
                    product=self.stack, sku=f"MS-{c.value[:3].upper()}-{s.value}", price=Decimal("419"), stock_quantity=0,
                )
                variant.attribute_values.add(c, s)
                self.v[(c.value, s.value)] = variant
        services.receive_stock(variant_id=self.v[("Violet", "2-4")].id, warehouse_id=self.puri.id, quantity=3)

        self.plain = self._simple("Laal Noor", "LN-BNGLS")
        self.draft = self._simple("New Kada", "NK-BNGLS", active=False)
        self.gone = self._simple("Old Kada", "OK-BNGLS")
        catalog_services.soft_delete_product(product=self.gone.product)

    def _simple(self, name, sku, active=True):
        product = Product.objects.create(name=name, slug=sku.lower(), category=self.category, is_active=active)
        return ProductVariant.objects.create(product=product, sku=sku, price=Decimal("399"), stock_quantity=0, is_default=True)

    def _on_hand(self, variant):
        row = WarehouseStock.objects.filter(variant=variant, warehouse=self.puri).first()
        return row.on_hand if row else 0

    def test_receives_every_line_with_its_own_ledger_entry(self):
        response = self.client.post(URL, {
            "warehouse_id": str(self.puri.id),
            "reference_id": "Bill #AB-2291",
            "notes": "Diwali restock",
            "items": [
                {"variant_id": str(self.v[("Violet", "2-4")].id), "quantity": 2},
                {"variant_id": str(self.v[("Rust", "2-6")].id), "quantity": 5},
                {"variant_id": str(self.plain.id), "quantity": 4},
                {"variant_id": str(self.draft.id), "quantity": 1},
            ],
        }, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        data = response.data["data"]
        self.assertEqual((data["total_quantity"], data["variants"], data["products"]), (12, 4, 3))
        self.assertEqual(self._on_hand(self.v[("Violet", "2-4")]), 5)
        self.assertEqual(self._on_hand(self.v[("Rust", "2-6")]), 5)
        self.assertEqual(self._on_hand(self.plain), 4)
        self.assertEqual(self._on_hand(self.draft), 1)
        self.assertEqual(StockLedger.objects.filter(reference_id="Bill #AB-2291").count(), 4)

    def test_same_variant_twice_is_added_together(self):
        variant = self.v[("Rust", "2-4")]
        self.client.post(URL, {"warehouse_id": str(self.puri.id), "items": [
            {"variant_id": str(variant.id), "quantity": 2}, {"variant_id": str(variant.id), "quantity": 3},
        ]}, format="json")
        self.assertEqual(self._on_hand(variant), 5)
        self.assertEqual(StockLedger.objects.filter(stock_record__variant=variant).count(), 1)

    def test_one_bad_line_saves_nothing(self):
        before = StockLedger.objects.count()
        response = self.client.post(URL, {"warehouse_id": str(self.puri.id), "items": [
            {"variant_id": str(self.plain.id), "quantity": 4},
            {"variant_id": str(self.gone.id), "quantity": 1},  # deleted product
        ]}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self._on_hand(self.plain), 0)
        self.assertEqual(StockLedger.objects.count(), before)

    def test_zero_or_negative_quantity_is_refused(self):
        response = self.client.post(URL, {"warehouse_id": str(self.puri.id), "items": [
            {"variant_id": str(self.plain.id), "quantity": 0},
        ]}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_inactive_warehouse_is_refused(self):
        response = self.client.post(URL, {"warehouse_id": str(self.closed.id), "items": [
            {"variant_id": str(self.plain.id), "quantity": 1},
        ]}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(StockLedger.objects.count(), 1)  # only the setUp receive

    def test_customers_cannot_use_it(self):
        customer = User.objects.create_user(email="c@example.com", password="pw123456")
        self.client.force_authenticate(user=customer)
        self.assertEqual(self.client.get(CATALOG_URL).status_code, 403)
        response = self.client.post(URL, {"warehouse_id": str(self.puri.id), "items": [
            {"variant_id": str(self.plain.id), "quantity": 1},
        ]}, format="json")
        self.assertEqual(response.status_code, 403)

    def test_catalog_has_options_swatches_and_stock_and_skips_deleted(self):
        response = self.client.get(CATALOG_URL, {"warehouse_id": str(self.puri.id)})
        self.assertEqual(response.status_code, 200, response.data)
        products = {p["name"]: p for p in response.data["data"]}
        self.assertEqual(set(products), {"Marble Stack", "Laal Noor", "New Kada"})
        self.assertFalse(products["New Kada"]["is_active"])

        stack = products["Marble Stack"]
        colour = next(a for a in stack["attributes"] if a["name"] == "Color")
        self.assertTrue(colour["show_swatches"])
        self.assertIn({"value": "Rust", "hex_code": "#B7410E"}, colour["values"])
        violet24 = next(v for v in stack["variants"] if v["sku"] == "MS-VIO-2-4")
        self.assertEqual(violet24["on_hand"], 3)
        self.assertCountEqual(
            [(o["attribute"], o["value"]) for o in violet24["options"]], [("Color", "Violet"), ("Size", "2-4")],
        )

    def test_catalog_query_count_does_not_grow_per_product(self):
        with CaptureQueriesContext(connection) as few:
            self.client.get(CATALOG_URL, {"warehouse_id": str(self.puri.id)})
        for i in range(8):
            self._simple(f"Extra {i}", f"EX-{i}")
        with CaptureQueriesContext(connection) as many:
            self.client.get(CATALOG_URL, {"warehouse_id": str(self.puri.id)})
        self.assertEqual(len(few.captured_queries), len(many.captured_queries))
