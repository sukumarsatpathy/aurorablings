"""
Finding stock by its label: a scanned barcode, or a product's stock ID.

Exact matches only, and OR'd onto the existing text search — so these tests
also pin that a normal name/SKU search still returns what it always did.
"""

from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User, UserRole
from apps.catalog.models import Category, Product, ProductVariant
from apps.inventory import selectors
from apps.inventory.models import Warehouse, WarehouseStock


class BarcodeSearchTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name="Earrings", slug="earrings")
        self.studs = Product.objects.create(
            name="Aurora Studs", slug="aurora-studs", category=category, is_active=True, stock_id=12,
        )
        self.hoops = Product.objects.create(
            name="Moon Hoops", slug="moon-hoops", category=category, is_active=True,
        )
        self.studs_v = ProductVariant.objects.create(
            product=self.studs, sku="EAR-001", price=Decimal("349"), is_active=True, is_default=True,
        )
        self.hoops_v = ProductVariant.objects.create(
            product=self.hoops, sku="EAR-002", price=Decimal("499"), is_active=True, is_default=True,
        )
        self.studs_v.refresh_from_db()
        self.hoops_v.refresh_from_db()
        warehouse = Warehouse.objects.create(name="Puri", code="puri", is_active=True, is_default=True)
        for v in (self.studs_v, self.hoops_v):
            WarehouseStock.objects.create(variant=v, warehouse=warehouse, on_hand=5, reserved=0, available=5)

    def stock_skus(self, search):
        return sorted(r.variant.sku for r in selectors.get_all_stock_records(search=search))

    def option_skus(self, search):
        return sorted(v.sku for v in selectors.get_variant_options(search=search))

    def test_every_variant_has_a_barcode(self):
        self.assertTrue(self.studs_v.barcode)
        self.assertNotEqual(self.studs_v.barcode, self.hoops_v.barcode)

    def test_a_scanned_barcode_finds_exactly_that_variant(self):
        self.assertEqual(self.stock_skus(self.hoops_v.barcode), ["EAR-002"])
        self.assertEqual(self.option_skus(self.hoops_v.barcode), ["EAR-002"])

    def test_a_partial_barcode_is_not_a_match(self):
        partial = self.hoops_v.barcode[:-2]
        self.assertEqual(self.stock_skus(partial), [])

    def test_stock_id_finds_the_product(self):
        self.assertEqual(self.stock_skus("12"), ["EAR-001"])
        self.assertEqual(self.option_skus("12"), ["EAR-001"])

    def test_text_search_is_unchanged(self):
        self.assertEqual(self.stock_skus("hoops"), ["EAR-002"])
        self.assertEqual(self.stock_skus("EAR-00"), ["EAR-001", "EAR-002"])
        self.assertEqual(self.option_skus("aurora"), ["EAR-001"])

    def test_a_huge_number_does_not_error(self):
        self.assertEqual(self.stock_skus("412345678901234"), [])

    def test_variant_options_api_returns_barcode_and_stock_id(self):
        admin = User.objects.create_user(
            email="owner@aurorablings.com", password="x", first_name="O", last_name="W", role=UserRole.ADMIN,
        )
        client = APIClient()
        client.force_authenticate(admin)
        res = client.get("/api/v1/inventory/stock/variants/", {"search": self.studs_v.barcode})
        rows = res.data["data"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["barcode"], self.studs_v.barcode)
        self.assertEqual(rows[0]["stock_id"], 12)

    def test_admin_product_list_carries_skus_and_barcodes(self):
        admin = User.objects.create_user(
            email="owner2@aurorablings.com", password="x", first_name="O", last_name="W", role=UserRole.ADMIN,
        )
        client = APIClient()
        client.force_authenticate(admin)
        res = client.get("/api/v1/catalog/products/", {"include_drafts": "true", "page_size": 50})
        payload = res.data.get("data", res.data)
        rows = payload.get("results", payload) if isinstance(payload, dict) else payload
        studs = next(r for r in rows if r["name"] == "Aurora Studs")
        self.assertEqual(studs["skus"], ["EAR-001"])
        self.assertEqual(studs["barcodes"], [self.studs_v.barcode])

    def test_the_public_product_list_does_not_expose_them(self):
        res = APIClient().get("/api/v1/catalog/products/")
        payload = res.data.get("data", res.data)
        rows = payload.get("results", payload) if isinstance(payload, dict) else payload
        self.assertTrue(rows)
        self.assertNotIn("barcodes", rows[0])
