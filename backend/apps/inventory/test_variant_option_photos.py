"""
The Receive/Adjust stock variant picker shows each variant's own colour photo.
"""

import shutil
import tempfile
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APITestCase

from apps.catalog.models import Attribute, AttributeValue, Category, Product, ProductMedia, ProductVariant
from apps.catalog.tests import make_image_file

User = get_user_model()
URL = "/api/v1/inventory/stock/variants/"


class VariantOptionPhotoTests(APITestCase):
    def setUp(self):
        tmp = tempfile.mkdtemp(prefix="aurora-inv-photos-")
        override = override_settings(MEDIA_ROOT=tmp)
        override.enable()
        self.addCleanup(override.disable)
        self.addCleanup(lambda: shutil.rmtree(tmp, ignore_errors=True))
        admin = User.objects.create_user(email="a-inv@example.com", password="pw123456", role="admin", is_staff=True, is_superuser=True)
        self.client.force_authenticate(user=admin)

        category = Category.objects.create(name="Bangles", slug="bangles")
        self.product = Product.objects.create(name="Marble Stack", slug="marble-stack", category=category, is_active=True)
        colour = Attribute.objects.create(product=self.product, name="Color")
        size = Attribute.objects.create(product=self.product, name="Size")
        self.amber = AttributeValue.objects.create(attribute=colour, value="Amber Orange")
        self.blush = AttributeValue.objects.create(attribute=colour, value="Blush Pink")
        self.rust = AttributeValue.objects.create(attribute=colour, value="Rust")
        s24 = AttributeValue.objects.create(attribute=size, value="2-4")
        self.s24 = s24
        self.s26 = AttributeValue.objects.create(attribute=size, value="2-6")

        self.main = self._photo("main.jpg", primary=True, order=0)
        self.amber_photo = self._photo("amber.jpg", order=1, tag=self.amber)
        self.blush_photo = self._photo("blush.jpg", order=2, tag=self.blush)
        for colour_value in (self.amber, self.blush, self.rust):
            v = ProductVariant.objects.create(
                product=self.product, sku=f"MS-{colour_value.value[:3].upper()}", price=Decimal("419"),
                stock_quantity=1, is_default=colour_value == self.amber,
            )
            v.attribute_values.add(colour_value, s24)

    def _photo(self, name, *, primary=False, order=0, tag=None):
        media = ProductMedia(product=self.product, alt_text=name, is_primary=primary, sort_order=order)
        media.image = make_image_file(name)
        media.save()
        tags = tag if isinstance(tag, (list, tuple)) else ([tag] if tag else [])
        if tags:
            media.attribute_values.set(tags)
        return media

    def _images(self):
        response = self.client.get(URL)
        self.assertEqual(response.status_code, 200, response.data)
        return {row["sku"]: row["product_image"] for row in response.data["data"]}

    def _url_of(self, media):
        media.refresh_from_db()
        return (media.image_small or media.image).url

    def test_each_colour_gets_its_own_photo(self):
        images = self._images()
        self.assertTrue(images["MS-AMB"].endswith(self._url_of(self.amber_photo)))
        self.assertTrue(images["MS-BLU"].endswith(self._url_of(self.blush_photo)))
        # No Rust photo tagged: falls back to the product's main photo.
        self.assertTrue(images["MS-RUS"].endswith(self._url_of(self.main)))

    def test_query_count_does_not_grow_with_variants(self):
        with CaptureQueriesContext(connection) as few:
            self.client.get(URL)
        for i in range(10):
            v = ProductVariant.objects.create(product=self.product, sku=f"MS-X{i}", price=Decimal("1"), stock_quantity=1)
            v.attribute_values.add(self.rust)
        with CaptureQueriesContext(connection) as many:
            self.client.get(URL)
        self.assertEqual(len(few.captured_queries), len(many.captured_queries))

    def test_combination_photo_beats_colour_photo(self):
        # Blush in 2-6 has its own photo; Blush in 2-4 keeps the Blush photo.
        combo = self._photo("blush-26.jpg", order=3, tag=[self.blush, self.s26])
        v = ProductVariant.objects.create(product=self.product, sku="MS-BLU26", price=Decimal("419"), stock_quantity=1)
        v.attribute_values.add(self.blush, self.s26)
        images = self._images()
        self.assertTrue(images["MS-BLU26"].endswith(self._url_of(combo)))
        self.assertTrue(images["MS-BLU"].endswith(self._url_of(self.blush_photo)))

    def test_size_only_photo_fits_every_colour_in_that_size(self):
        size_photo = self._photo("size-24.jpg", order=4, tag=self.s24)
        images = self._images()
        # Rust has no colour photo, but it is 2-4.
        self.assertTrue(images["MS-RUS"].endswith(self._url_of(size_photo)))
        # A tie between a colour photo and a size photo goes to sort order.
        self.assertTrue(images["MS-AMB"].endswith(self._url_of(self.amber_photo)))
