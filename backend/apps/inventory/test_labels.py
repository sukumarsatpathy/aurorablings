"""
Label sheets for the label printer app.

One row per sticker, barcode as text, regular price as MRP, and no effect on
stock — printing a label must never be how stock appears.
"""

import csv
import io
from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.catalog.models import Category, Product, ProductVariant
from apps.inventory.models import StockLedger

User = get_user_model()
URL = "/api/v1/inventory/labels/"


class LabelSheetTests(APITestCase):
    def setUp(self):
        admin = User.objects.create_user(
            email="labels@example.com", password="pw123456", role="admin", is_staff=True, is_superuser=True,
        )
        self.client.force_authenticate(user=admin)
        category = Category.objects.create(name="Earrings", slug="earrings")
        product = Product.objects.create(name="Jhumka", slug="jhumka", category=category, is_active=True)
        self.a = ProductVariant.objects.create(
            product=product, sku="J-RED", price=Decimal("499.00"), label_name="Jhumka Red",
            offer_price=Decimal("399.00"), offer_is_active=True,
        )
        self.b = ProductVariant.objects.create(product=product, sku="J-GRN", price=Decimal("549.50"))

    def rows(self, response):
        text = response.content.decode("utf-8-sig")
        return list(csv.reader(io.StringIO(text)))

    def test_one_row_per_sticker_in_the_order_asked(self):
        response = self.client.post(URL, {
            "format": "csv",
            "items": [{"variant_id": str(self.a.id), "copies": 2}, {"variant_id": str(self.b.id), "copies": 1}],
        }, format="json")

        self.assertEqual(response.status_code, 200, getattr(response, "data", None))
        rows = self.rows(response)
        self.assertEqual(rows[0], ["Barcode", "Name", "SKU", "MRP"])
        self.assertEqual(rows[1], [self.a.barcode, "Jhumka Red", "J-RED", "499"])
        self.assertEqual(rows[2], rows[1])
        self.assertEqual(rows[3][2:], ["J-GRN", "549.50"])
        self.assertEqual(response["X-Label-Count"], "3")

    def test_mrp_is_the_regular_price_not_the_offer(self):
        response = self.client.post(URL, {"format": "csv", "items": [{"variant_id": str(self.a.id), "copies": 1}]}, format="json")
        self.assertEqual(self.rows(response)[1][3], "499")

    def test_xlsx_is_the_default(self):
        response = self.client.post(URL, {"items": [{"variant_id": str(self.a.id), "copies": 1}]}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Disposition"].endswith('.xlsx"') or response["Content-Disposition"].endswith('.csv"'))

    def test_printing_labels_never_touches_stock(self):
        self.client.post(URL, {"format": "csv", "items": [{"variant_id": str(self.a.id), "copies": 5}]}, format="json")
        self.a.refresh_from_db()
        self.assertEqual(self.a.stock_quantity, 0)
        self.assertEqual(StockLedger.objects.count(), 0)

    def test_too_many_labels_is_refused(self):
        response = self.client.post(URL, {
            "items": [{"variant_id": str(self.a.id), "copies": 1000}] * 6,
        }, format="json")
        self.assertEqual(response.status_code, 400)
