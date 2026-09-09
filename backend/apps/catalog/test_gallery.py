"""
The card hover gallery endpoint.

It exists so a product card can show a second photograph without dragging the
entire product detail — variants, attributes, info items — across the wire once
per hovered card. It must also refuse exactly what the rest of the storefront
refuses: drafts and deleted products.
"""

import shutil
import tempfile

from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.catalog.models import Category, Product, ProductMedia
from apps.catalog.tests import make_image_file


class ProductGalleryTests(APITestCase):
    def setUp(self):
        self._tmp_media = tempfile.mkdtemp(prefix="aurora-gallery-tests-")
        self.override_media = override_settings(MEDIA_ROOT=self._tmp_media)
        self.override_media.enable()
        self.addCleanup(self.override_media.disable)
        self.addCleanup(lambda: shutil.rmtree(self._tmp_media, ignore_errors=True))

        self.category = Category.all_objects.create(name="Bangles", slug="bangles", is_active=True)
        self.product = Product.all_objects.create(
            name="Laal Noor", slug="laal-noor", category=self.category, is_active=True,
        )
        # Deliberately out of order: the primary is created last and sits at a
        # higher sort_order, so "first row wins" would return the wrong picture.
        self.second = ProductMedia.objects.create(
            product=self.product, image=make_image_file("second.jpg"), sort_order=1,
        )
        self.third = ProductMedia.objects.create(
            product=self.product, image=make_image_file("third.jpg"), sort_order=2,
        )
        self.primary = ProductMedia.objects.create(
            product=self.product, image=make_image_file("primary.jpg"),
            is_primary=True, sort_order=9,
        )

    def url(self, product=None):
        return f"/api/v1/catalog/products/{(product or self.product).id}/gallery/"

    def test_anyone_can_fetch_a_published_product_gallery(self):
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(len(response.data["data"]), 3)

    def test_the_primary_image_comes_first(self):
        rows = self.client.get(self.url()).data["data"]
        self.assertEqual(rows[0]["id"], str(self.primary.id))
        self.assertTrue(rows[0]["is_primary"])
        self.assertEqual([r["id"] for r in rows[1:]], [str(self.second.id), str(self.third.id)])

    def test_the_medium_rendition_is_served(self):
        """
        The card renders at a few hundred CSS px. If this stops carrying
        image_medium the hook silently falls back to the 1800px master.
        """
        rows = self.client.get(self.url()).data["data"]
        self.assertIn("image_medium", rows[0])
        self.assertTrue(rows[0]["image_medium"])

    def test_a_draft_product_has_no_public_gallery(self):
        Product.all_objects.filter(pk=self.product.pk).update(is_active=False)
        self.assertEqual(self.client.get(self.url()).status_code, status.HTTP_404_NOT_FOUND)

    def test_a_deleted_product_has_no_public_gallery(self):
        Product.all_objects.filter(pk=self.product.pk).update(deleted_at=timezone.now())
        self.assertEqual(self.client.get(self.url()).status_code, status.HTTP_404_NOT_FOUND)
