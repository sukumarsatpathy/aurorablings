"""
The counter's stock reference number.

Two things matter here: no two products may claim the same number (a staff
member typing one into the till must land on one piece), and the number must
actually be searchable from the counter — including the case that would
otherwise be a database error rather than an empty result, a query of pure
digits against an integer column.
"""

from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User, UserRole
from apps.catalog.models import Category, Product, ProductVariant


class StockIdWriteTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email="owner@aurorablings.com", password="x", first_name="S", last_name="S",
            role=UserRole.ADMIN,
        )
        self.client.force_authenticate(self.admin)
        self.category = Category.objects.create(name="Necklaces", slug="necklaces")
        self.existing = Product.objects.create(
            name="Aurora Necklace", slug="aurora-necklace",
            category=self.category, stock_id=1042,
        )
        self.url = "/api/v1/catalog/products/"

    def test_a_product_can_be_created_with_a_stock_id(self):
        response = self.client.post(
            self.url,
            {"name": "Kundan ring", "category_id": str(self.category.id), "stock_id": 2001},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["data"]["stock_id"], 2001)

    def test_a_product_needs_no_stock_id(self):
        response = self.client.post(
            self.url, {"name": "Plain ring", "category_id": str(self.category.id)}, format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertIsNone(response.data["data"]["stock_id"])

    def test_two_products_cannot_share_a_number(self):
        """A validation error naming the clash, not a 500 from the constraint."""
        response = self.client.post(
            self.url,
            {"name": "Clashing ring", "category_id": str(self.category.id), "stock_id": 1042},
            format="json",
        )
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("Aurora Necklace", str(response.data))
        self.assertEqual(Product.all_objects.filter(stock_id=1042).count(), 1)

    def test_saving_a_product_without_changing_its_number_is_not_a_clash(self):
        response = self.client.patch(
            f"{self.url}{self.existing.id}/",
            {"name": "Aurora Necklace II", "stock_id": 1042},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.existing.refresh_from_db()
        self.assertEqual(self.existing.stock_id, 1042)

    def test_the_number_can_be_cleared(self):
        response = self.client.patch(
            f"{self.url}{self.existing.id}/", {"stock_id": None}, format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.existing.refresh_from_db()
        self.assertIsNone(self.existing.stock_id)

    def test_several_products_may_sit_without_a_number(self):
        Product.objects.create(name="A", slug="a", category=self.category)
        Product.objects.create(name="B", slug="b", category=self.category)
        self.assertEqual(Product.all_objects.filter(stock_id__isnull=True).count(), 2)


class StockIdCounterSearchTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.staff = User.objects.create_user(
            email="priya@aurorablings.com", password="x", first_name="P", last_name="S",
            role=UserRole.STAFF,
        )
        self.client.force_authenticate(self.staff)

        self.category = Category.objects.create(name="Necklaces", slug="necklaces")
        self.tagged = Product.objects.create(
            name="Aurora Necklace", slug="aurora-necklace",
            category=self.category, is_active=True, stock_id=1042,
        )
        self.other = Product.objects.create(
            name="Kundan ring", slug="kundan-ring",
            category=self.category, is_active=True, stock_id=2001,
        )
        for product, sku in ((self.tagged, "NECK-001"), (self.other, "RING-001")):
            ProductVariant.objects.create(
                product=product, sku=sku, price=Decimal("1850.00"),
                is_active=True, is_default=True,
            )
        self.url = reverse("pos:catalogue")

    def search(self, q):
        response = self.client.get(self.url, {"q": q})
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def test_typing_a_stock_id_finds_that_product(self):
        rows = self.search("1042")
        self.assertEqual([r["product_name"] for r in rows], ["Aurora Necklace"])
        self.assertEqual(rows[0]["stock_id"], 1042)

    def test_a_stock_id_that_matches_nothing_returns_nothing(self):
        self.assertEqual(self.search("9999"), [])

    def test_a_numeric_query_still_searches_names_and_skus(self):
        """
        The digits branch is OR'd in, not swapped for the text search — "001" is
        both a plausible stock number and part of every SKU here.
        """
        rows = self.search("001")
        self.assertEqual(len(rows), 2)

    def test_rows_carry_the_stock_id_even_when_unset(self):
        Product.objects.filter(pk=self.other.pk).update(stock_id=None)
        rows = self.search("Kundan")
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]["stock_id"])

    def test_a_draft_product_is_not_reachable_by_its_stock_id(self):
        Product.objects.filter(pk=self.tagged.pk).update(is_active=False)
        self.assertEqual(self.search("1042"), [])
