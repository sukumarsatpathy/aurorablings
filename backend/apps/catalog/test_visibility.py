"""
Draft visibility, and the bulk status change that produces drafts.

The bug these pin: visibility used to key off the session, so an admin browsing
their own shop while signed in saw inactive products on the home page and the
listing. The person best placed to notice was the only person who couldn't.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from apps.catalog.models import Category, Product

User = get_user_model()

PRODUCTS_URL = "/api/v1/catalog/products/"
BULK_URL = "/api/v1/catalog/products/bulk-status/"


def _rows(response):
    payload = response.data
    data = payload.get("data", payload) if isinstance(payload, dict) else payload
    if isinstance(data, dict):
        return data.get("results", data.get("data", []))
    return data


class DraftVisibilityTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="owner@aurorablings.com", password="password123", role="admin",
        )
        self.shopper = User.objects.create_user(
            email="shopper@example.com", password="password123", role="customer",
        )
        self.category = Category.all_objects.create(name="Rings", slug="rings", is_active=True)
        self.live = Product.all_objects.create(
            name="Kundan ring", slug="kundan-ring", category=self.category, is_active=True,
        )
        self.draft = Product.all_objects.create(
            name="Unfinished ring", slug="unfinished-ring", category=self.category, is_active=False,
        )

    def _names(self, response):
        return {row["name"] for row in _rows(response)}

    def test_anonymous_listing_hides_drafts(self):
        names = self._names(self.client.get(PRODUCTS_URL))
        self.assertIn("Kundan ring", names)
        self.assertNotIn("Unfinished ring", names)

    def test_a_signed_in_admin_browsing_the_shop_sees_what_a_shopper_sees(self):
        self.client.force_authenticate(self.admin)
        names = self._names(self.client.get(PRODUCTS_URL))
        self.assertNotIn("Unfinished ring", names)

    def test_the_admin_screen_asks_for_drafts_and_gets_them(self):
        self.client.force_authenticate(self.admin)
        names = self._names(self.client.get(PRODUCTS_URL, {"include_drafts": "true"}))
        self.assertIn("Unfinished ring", names)

    def test_a_shopper_cannot_ask_for_drafts(self):
        self.client.force_authenticate(self.shopper)
        names = self._names(self.client.get(PRODUCTS_URL, {"include_drafts": "true"}))
        self.assertNotIn("Unfinished ring", names)

    def test_a_draft_is_not_reachable_by_id_or_slug(self):
        self.assertEqual(
            self.client.get(f"{PRODUCTS_URL}{self.draft.id}/").status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.get(f"{PRODUCTS_URL}slug/{self.draft.slug}/").status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_staff_can_still_open_a_draft_by_id_when_they_ask(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(f"{PRODUCTS_URL}{self.draft.id}/", {"include_drafts": "true"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class BulkStatusTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="owner@aurorablings.com", password="password123", role="admin",
        )
        self.shopper = User.objects.create_user(
            email="shopper@example.com", password="password123", role="customer",
        )
        self.category = Category.all_objects.create(name="Rings", slug="rings", is_active=True)
        self.a = Product.all_objects.create(
            name="Ring A", slug="ring-a", category=self.category, is_active=True,
        )
        self.b = Product.all_objects.create(
            name="Ring B", slug="ring-b", category=self.category, is_active=True,
        )

    def test_a_shopper_cannot_change_product_status(self):
        self.client.force_authenticate(self.shopper)
        response = self.client.post(
            BULK_URL, {"ids": [str(self.a.id)], "is_active": False}, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.a.refresh_from_db()
        self.assertTrue(self.a.is_active)

    def test_admin_moves_several_products_to_draft_at_once(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            BULK_URL,
            {"ids": [str(self.a.id), str(self.b.id)], "is_active": False},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.a.refresh_from_db()
        self.b.refresh_from_db()
        self.assertFalse(self.a.is_active)
        self.assertFalse(self.b.is_active)

    def test_drafted_products_leave_the_storefront_immediately(self):
        self.client.force_authenticate(self.admin)
        self.client.post(BULK_URL, {"ids": [str(self.a.id)], "is_active": False}, format="json")

        self.client.force_authenticate(user=None)
        names = {row["name"] for row in _rows(self.client.get(PRODUCTS_URL))}
        self.assertNotIn("Ring A", names)
        self.assertIn("Ring B", names)

    def test_an_already_active_product_counts_as_unchanged(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            BULK_URL, {"ids": [str(self.a.id)], "is_active": True}, format="json",
        )
        self.assertEqual(response.data["data"]["updated"], 0)
        self.assertEqual(response.data["data"]["unchanged"], 1)

    def test_a_soft_deleted_product_is_never_republished(self):
        self.a.deleted_at = self.a.created_at
        self.a.is_active = False
        self.a.save(update_fields=["deleted_at", "is_active"])
        self.client.force_authenticate(self.admin)

        response = self.client.post(
            BULK_URL, {"ids": [str(self.a.id)], "is_active": True}, format="json",
        )

        self.assertEqual(response.data["data"]["updated"], 0)
        self.assertEqual(response.data["data"]["skipped"], [str(self.a.id)])
        self.a.refresh_from_db()
        self.assertFalse(self.a.is_active)

    def test_an_empty_selection_is_rejected(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(BULK_URL, {"ids": [], "is_active": False}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
