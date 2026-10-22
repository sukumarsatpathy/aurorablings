"""
A deleted product's stock disappears from the Inventory page and its totals,
and comes back unchanged if the product is restored. Drafts still show.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.catalog import services as catalog_services
from apps.catalog.models import Category, Product, ProductVariant
from apps.inventory import selectors, services
from apps.inventory.models import Warehouse

User = get_user_model()
STOCK_URL = "/api/v1/inventory/stock/"


class DeletedProductStockTests(APITestCase):
    def setUp(self):
        admin = User.objects.create_user(
            email="admin-inv@example.com", password="password123",
            role="admin", is_staff=True, is_superuser=True,
        )
        self.client.force_authenticate(user=admin)
        self.warehouse = Warehouse.objects.create(name="Puri", code="puri-wrhs", is_default=True)
        category = Category.objects.create(name="Bangles", slug="bangles")
        self.live = self._product("Laal Noor", "laal-noor", category, qty=1)       # low stock
        self.gone = self._product("Old Kada", "old-kada", category, qty=2)         # will be deleted
        self.draft = self._product("New Kada", "new-kada", category, qty=3, active=False)

    def _product(self, name, slug, category, *, qty, active=True):
        product = Product.objects.create(name=name, slug=slug, category=category, is_active=active)
        variant = ProductVariant.objects.create(
            product=product, sku=slug.upper(), price=Decimal("399"), stock_quantity=0, is_default=True,
        )
        services.receive_stock(variant_id=variant.id, warehouse_id=self.warehouse.id, quantity=qty)
        return product

    def test_deleted_product_stock_is_hidden_and_comes_back_on_restore(self):
        catalog_services.soft_delete_product(product=self.gone)

        skus = {r.variant.sku for r in selectors.get_all_stock_records()}
        self.assertEqual(skus, {"LAAL-NOOR", "NEW-KADA"})  # draft still listed
        self.assertNotIn("OLD-KADA", {r.variant.sku for r in selectors.get_low_stock_records()})
        self.assertNotIn("OLD-KADA", {r.variant.sku for r in selectors.get_all_stock_records(search="Old")})

        response = self.client.get(STOCK_URL)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(response.data["data"]), 2)

        gone = Product.all_objects.get(pk=self.gone.pk)
        catalog_services.restore_product(product=gone)
        restored = [r for r in selectors.get_all_stock_records() if r.variant.sku == "OLD-KADA"]
        self.assertEqual(len(restored), 1)
        self.assertEqual(restored[0].on_hand, 2)

    def test_out_of_stock_ignores_deleted_products(self):
        services.adjust_stock(
            variant_id=self.gone.variants.get().id, warehouse_id=self.warehouse.id,
            quantity_delta=-2, reason="test",
        )
        self.assertIn("OLD-KADA", {r.variant.sku for r in selectors.get_out_of_stock_records()})
        catalog_services.soft_delete_product(product=self.gone)
        self.assertNotIn("OLD-KADA", {r.variant.sku for r in selectors.get_out_of_stock_records()})
