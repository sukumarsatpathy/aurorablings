"""
A deleted product must not be sellable.

Soft delete stamps `deleted_at` and leaves `is_active` True, so anything that
guards only on `is_active` still sees the product. That is how a product deleted
in the admin — gone from the shop, gone from the admin list — kept appearing on
the till, and could have been rung up and sold.
"""

from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User, UserRole
from apps.catalog.models import Category, Product, ProductVariant


class DeletedProductNotSellableTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.staff = User.objects.create_user(
            email="priya@aurorablings.com", password="x", first_name="P", last_name="S",
            role=UserRole.STAFF,
        )
        self.client.force_authenticate(self.staff)

        self.category = Category.objects.create(name="Bangles", slug="bangles")
        self.product = Product.objects.create(
            name="Rose Meher - Set of 2 Bangles", slug="rose-meher-bangles",
            category=self.category, is_active=True,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product, sku="RM-BNGLS", price=Decimal("399.00"),
            is_active=True, is_default=True,
        )
        self.url = reverse("pos:catalogue")

    def test_soft_delete_leaves_is_active_true(self):
        """The premise of the bug, pinned so the fix isn't quietly undone."""
        self.product.delete()
        self.product.refresh_from_db()
        self.assertTrue(self.product.is_active)
        self.assertIsNotNone(self.product.deleted_at)

    def test_the_counter_does_not_offer_a_deleted_product(self):
        self.assertEqual(len(self.client.get(self.url, {"q": "Rose"}).data), 1)

        self.product.delete()

        self.assertEqual(self.client.get(self.url, {"q": "Rose"}).data, [])

    def test_restoring_a_cart_does_not_bring_back_a_deleted_product(self):
        """
        The `ids` path re-reads price and stock for a cart the till already had.
        A product deleted mid-sale must drop out of it.
        """
        self.product.delete()
        response = self.client.get(self.url, {"ids": str(self.variant.id)})
        self.assertEqual(response.data, [])

    def test_a_deleted_product_cannot_be_rung_up(self):
        from django.core.exceptions import ValidationError as DjangoValidationError
        from rest_framework.exceptions import ValidationError as DRFValidationError

        from apps.orders.services import create_admin_order_from_items

        self.product.delete()

        with self.assertRaises((DjangoValidationError, DRFValidationError)):
            create_admin_order_from_items(
                items=[{"variant_id": str(self.variant.id), "quantity": 1}],
                contact={"name": "Walk-in", "phone": "9999999999"},
            )
