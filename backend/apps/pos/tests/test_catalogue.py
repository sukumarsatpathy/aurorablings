"""
What the till is told about stock.

Stock has two homes in this codebase: WarehouseStock rows in the inventory app,
and the legacy `stock_quantity` column on the variant. The storefront reads
ProductVariant.available_quantity, which prefers the warehouse rows. If the POS
catalogue reads the column instead, every variant inventory manages reads as
zero and the counter refuses to sell things that are sitting on the table.

These tests pin the till to the same source as the storefront.
"""

from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User, UserRole
from apps.catalog.models import Category, Product, ProductVariant
from apps.inventory.models import Warehouse, WarehouseStock


class CatalogueStockTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.staff = User.objects.create_user(
            email="priya@aurorablings.com", password="x", first_name="P", last_name="S",
            role=UserRole.STAFF,
        )
        self.client.force_authenticate(self.staff)

        self.category = Category.objects.create(name="Necklaces", slug="necklaces")
        self.product = Product.objects.create(
            name="Aurora Necklace", slug="aurora-necklace",
            category=self.category, is_active=True,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product, sku="NECK-001", price=Decimal("1850.00"),
            stock_quantity=0, low_stock_threshold=5, is_active=True, is_default=True,
        )
        self.warehouse = Warehouse.objects.create(
            name="Bhubaneswar", code="bbsr", is_active=True, is_default=True,
        )

    def row(self, **params):
        response = self.client.get(reverse("pos:catalogue"), params or {"q": "Aurora"})
        self.assertEqual(response.status_code, 200, response.data)
        rows = [r for r in response.data if r["sku"] == "NECK-001"]
        self.assertEqual(len(rows), 1, response.data)
        return rows[0]

    def stock(self, on_hand, reserved=0):
        WarehouseStock.objects.create(
            variant=self.variant, warehouse=self.warehouse,
            on_hand=on_hand, reserved=reserved, available=on_hand - reserved,
        )

    def test_warehouse_stock_wins_over_the_legacy_column(self):
        """The bug this file exists for: 12 in the warehouse, 0 in the column."""
        self.stock(12)

        row = self.row()

        self.assertEqual(row["stock"], 12)
        self.assertFalse(row["low_stock"])

    def test_it_matches_what_the_storefront_would_say(self):
        self.stock(12)

        self.assertEqual(self.row()["stock"], self.variant.available_quantity)

    def test_reserved_units_are_not_offered_to_the_counter(self):
        """Reserved stock belongs to a pending order, not to the person at the stall."""
        self.stock(12, reserved=10)

        self.assertEqual(self.row()["stock"], 2)

    def test_the_column_is_still_the_fallback_without_warehouse_rows(self):
        """Variants inventory has never touched must not read as out of stock."""
        ProductVariant.objects.filter(pk=self.variant.pk).update(stock_quantity=7)

        self.assertEqual(self.row()["stock"], 7)

    def test_stock_at_an_inactive_warehouse_does_not_count(self):
        self.warehouse.is_active = False
        self.warehouse.save(update_fields=["is_active"])
        self.stock(12)

        self.assertEqual(self.row()["stock"], 0)

    def test_every_row_carries_an_image_key(self):
        """
        Null is a fine answer; a missing key is not — the till renders from it,
        and a row without the key silently loses the picture for that product.
        """
        row = self.row()

        self.assertIn("image", row)
        self.assertIsNone(row["image"])

    def test_the_query_count_does_not_grow_with_the_number_of_rows(self):
        """
        A search returns up to 100 variants. Reading the image per row turns a
        stall's catalogue search into 100 round trips on a tethered tablet.

        Asserting the shape rather than an exact number: what must hold is that
        five rows and twenty-five cost the same, whatever the fixed overhead is.
        """
        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        def search_query_count():
            with CaptureQueriesContext(connection) as captured:
                response = self.client.get(reverse("pos:catalogue"), {"q": "Aurora"})
                self.assertEqual(response.status_code, 200)
            return len(captured)

        def add_variants(start, count):
            for i in range(start, start + count):
                ProductVariant.objects.create(
                    product=self.product, sku=f"NECK-{i:03d}",
                    price=Decimal("1850.00"), is_active=True,
                )

        add_variants(10, 5)
        few = search_query_count()

        add_variants(20, 20)
        many = search_query_count()

        self.assertEqual(few, many)

    def test_the_cart_restore_path_reads_the_same_source(self):
        """Restoring by id must not disagree with the search that added the line."""
        self.stock(12)

        self.assertEqual(self.row(ids=str(self.variant.id))["stock"], 12)
