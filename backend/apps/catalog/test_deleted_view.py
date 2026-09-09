"""
The admin's Deleted view, and restoring from it.

Soft-deleted products are invisible everywhere by design; this is the one place
they can be seen, and it is staff-only for the same reason drafts are.
"""

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.catalog.models import Category, Product

User = get_user_model()

PRODUCTS_URL = "/api/v1/catalog/products/"


def _rows(response):
    payload = response.data
    data = payload.get("data", payload) if isinstance(payload, dict) else payload
    if isinstance(data, dict):
        return data.get("results", data.get("data", []))
    return data


class DeletedProductViewTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="owner@aurorablings.com", password="password123", role="admin",
        )
        self.shopper = User.objects.create_user(
            email="shopper@example.com", password="password123", role="customer",
        )
        self.category = Category.all_objects.create(name="Bangles", slug="bangles", is_active=True)
        self.live = Product.all_objects.create(
            name="Laal Noor", slug="laal-noor", category=self.category, is_active=True,
        )
        self.deleted = Product.all_objects.create(
            name="Rose Meher", slug="rose-meher", category=self.category,
            is_active=True, deleted_at=timezone.now(),
        )

    def names(self, response):
        return {row["name"] for row in _rows(response)}

    def test_deleted_products_are_hidden_unless_asked_for(self):
        self.client.force_authenticate(self.admin)
        names = self.names(self.client.get(PRODUCTS_URL, {"include_drafts": "true"}))
        self.assertNotIn("Rose Meher", names)

    def test_an_admin_can_ask_to_see_them(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(PRODUCTS_URL, {"include_deleted": "true"})
        rows = {row["name"]: row for row in _rows(response)}
        self.assertIn("Rose Meher", rows)
        self.assertIsNotNone(rows["Rose Meher"]["deleted_at"])

    def test_a_shopper_cannot(self):
        self.client.force_authenticate(self.shopper)
        names = self.names(self.client.get(PRODUCTS_URL, {"include_deleted": "true"}))
        self.assertNotIn("Rose Meher", names)

    def test_anonymous_cannot(self):
        names = self.names(self.client.get(PRODUCTS_URL, {"include_deleted": "true"}))
        self.assertNotIn("Rose Meher", names)

    def test_restoring_brings_a_product_back_as_a_draft(self):
        """
        Not as it was. A deleted product usually still carries is_active=True,
        so restoring it unchanged would republish it to the storefront the
        moment someone clicked Restore.
        """
        self.client.force_authenticate(self.admin)
        response = self.client.post(f"{PRODUCTS_URL}{self.deleted.id}/restore/")

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.deleted.refresh_from_db()
        self.assertIsNone(self.deleted.deleted_at)
        self.assertFalse(self.deleted.is_active)

        # And it is still off the storefront.
        self.client.force_authenticate(user=None)
        self.assertNotIn("Rose Meher", self.names(self.client.get(PRODUCTS_URL)))

    def test_restoring_a_product_that_is_not_deleted_is_refused(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(f"{PRODUCTS_URL}{self.live.id}/restore/")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.live.refresh_from_db()
        self.assertTrue(self.live.is_active)

    def test_a_shopper_cannot_restore(self):
        self.client.force_authenticate(self.shopper)
        response = self.client.post(f"{PRODUCTS_URL}{self.deleted.id}/restore/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.deleted.refresh_from_db()
        self.assertIsNotNone(self.deleted.deleted_at)

    def test_bulk_status_still_refuses_to_touch_a_deleted_product(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            f"{PRODUCTS_URL}bulk-status/",
            {"ids": [str(self.deleted.id)], "is_active": True},
            format="json",
        )
        self.assertEqual(response.data["data"]["skipped"], [str(self.deleted.id)])


class DeleteSetsDraftTests(APITestCase):
    """
    Deleting takes a product off sale, and restoring asks what it comes back as.

    Before this, delete only stamped `deleted_at` and left `is_active` True, so
    the flag said "live" about a product nothing would sell. The two states can
    no longer disagree.
    """

    def setUp(self):
        self.admin = User.objects.create_user(
            email="owner@aurorablings.com", password="password123", role="admin",
        )
        self.client.force_authenticate(self.admin)
        self.category = Category.all_objects.create(name="Bangles", slug="bangles", is_active=True)
        self.product = Product.all_objects.create(
            name="Raat Rani", slug="raat-rani", category=self.category, is_active=True,
        )

    def test_deleting_a_product_also_takes_it_off_sale(self):
        response = self.client.delete(f"{PRODUCTS_URL}{self.product.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

        self.product.refresh_from_db()
        self.assertIsNotNone(self.product.deleted_at)
        self.assertFalse(self.product.is_active)

    def test_restore_defaults_to_draft(self):
        self.client.delete(f"{PRODUCTS_URL}{self.product.id}/")
        self.client.post(f"{PRODUCTS_URL}{self.product.id}/restore/")

        self.product.refresh_from_db()
        self.assertIsNone(self.product.deleted_at)
        self.assertFalse(self.product.is_active)

    def test_restore_can_publish_when_the_admin_asks_for_it(self):
        self.client.delete(f"{PRODUCTS_URL}{self.product.id}/")
        response = self.client.post(
            f"{PRODUCTS_URL}{self.product.id}/restore/", {"is_active": True}, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

        self.product.refresh_from_db()
        self.assertIsNone(self.product.deleted_at)
        self.assertTrue(self.product.is_active)

        # And a shopper can see it again.
        self.client.force_authenticate(user=None)
        names = {row["name"] for row in _rows(self.client.get(PRODUCTS_URL))}
        self.assertIn("Raat Rani", names)


class BulkDeleteTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="owner@aurorablings.com", password="password123", role="admin",
        )
        self.shopper = User.objects.create_user(
            email="shopper@example.com", password="password123", role="customer",
        )
        self.category = Category.all_objects.create(name="Bangles", slug="bangles", is_active=True)
        self.a = Product.all_objects.create(
            name="Laal Noor", slug="laal-noor", category=self.category, is_active=True,
        )
        self.b = Product.all_objects.create(
            name="Raat Rani", slug="raat-rani", category=self.category, is_active=True,
        )
        self.url = f"{PRODUCTS_URL}bulk-delete/"

    def test_a_shopper_cannot_delete_products(self):
        self.client.force_authenticate(self.shopper)
        response = self.client.post(self.url, {"ids": [str(self.a.id)]}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.a.refresh_from_db()
        self.assertIsNone(self.a.deleted_at)

    def test_admin_deletes_several_at_once_and_they_leave_the_storefront(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            self.url, {"ids": [str(self.a.id), str(self.b.id)]}, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["data"]["deleted"], 2)

        for product in (self.a, self.b):
            product.refresh_from_db()
            self.assertIsNotNone(product.deleted_at)
            self.assertFalse(product.is_active)

        self.client.force_authenticate(user=None)
        self.assertEqual(_rows(self.client.get(PRODUCTS_URL)), [])

    def test_an_already_deleted_product_is_skipped_not_deleted_twice(self):
        self.a.delete()
        first_stamp = Product.all_objects.get(pk=self.a.pk).deleted_at
        self.client.force_authenticate(self.admin)

        response = self.client.post(self.url, {"ids": [str(self.a.id)]}, format="json")

        self.assertEqual(response.data["data"]["deleted"], 0)
        self.assertEqual(response.data["data"]["skipped"], [str(self.a.id)])
        self.assertEqual(Product.all_objects.get(pk=self.a.pk).deleted_at, first_stamp)

    def test_an_empty_selection_is_rejected(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(self.url, {"ids": []}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
