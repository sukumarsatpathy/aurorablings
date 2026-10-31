"""
Product photos can be tagged with options (e.g. Color: Violet, or Violet +
Size 2-6) so the product page shows those photos when a shopper picks them.

What matters: the tags are saved on upload and can be changed or cleared
later, an option from another product is refused, two options of one
attribute are refused, deleting an option keeps the photo (it just loses that
tag), and the public product data carries the tags.
"""

import shutil
import tempfile
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from apps.catalog.models import (
    Attribute, AttributeValue, Category, Product, ProductMedia, ProductVariant,
)
from apps.catalog.tests import make_image_file

User = get_user_model()


class MediaColourTagTests(APITestCase):
    def setUp(self):
        tmp = tempfile.mkdtemp(prefix="aurora-media-colour-")
        override = override_settings(MEDIA_ROOT=tmp)
        override.enable()
        self.addCleanup(override.disable)
        self.addCleanup(lambda: shutil.rmtree(tmp, ignore_errors=True))

        admin = User.objects.create_user(
            email="admin-colour@example.com", password="password123",
            role="admin", is_staff=True, is_superuser=True,
        )
        self.client.force_authenticate(user=admin)

        category = Category.objects.create(name="Bangles", slug="bangles")
        self.product = Product.objects.create(name="Noor Kada", slug="noor-kada", category=category, is_active=True)
        colour = Attribute.objects.create(product=self.product, name="Color")
        self.violet = AttributeValue.objects.create(attribute=colour, value="Violet")
        self.beige = AttributeValue.objects.create(attribute=colour, value="Beige")
        size = Attribute.objects.create(product=self.product, name="Size")
        self.s26 = AttributeValue.objects.create(attribute=size, value="2-6")
        variant = ProductVariant.objects.create(
            product=self.product, sku="NOOR-V", price=Decimal("499.00"), stock_quantity=3,
            is_active=True, is_default=True,
        )
        variant.attribute_values.add(self.violet)

        other = Product.objects.create(name="Other", slug="other", category=category, is_active=True)
        self.foreign_value = AttributeValue.objects.create(
            attribute=Attribute.objects.create(product=other, name="Color"), value="Violet",
        )
        self.media_url = f"/api/v1/catalog/products/{self.product.id}/media/"

    def _upload(self, **extra):
        return self.client.post(
            self.media_url, {"image": make_image_file("p.jpg"), **extra}, format="multipart",
        )

    def test_upload_with_colour_is_tagged(self):
        response = self._upload(attribute_value_id=str(self.violet.id))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(str(response.data["data"]["attribute_value"]), str(self.violet.id))
        self.assertEqual(list(ProductMedia.objects.get().attribute_values.all()), [self.violet])

    def test_upload_without_colour_is_untagged(self):
        response = self._upload()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsNone(response.data["data"]["attribute_value"])

    def test_option_from_another_product_is_refused(self):
        response = self._upload(attribute_value_id=str(self.foreign_value.id))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(ProductMedia.objects.exists())

    def test_garbage_id_is_refused(self):
        response = self._upload(attribute_value_id="not-a-uuid")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_patch_changes_and_clears_tag(self):
        media_id = self._upload(attribute_value_id=str(self.violet.id)).data["data"]["id"]
        url = f"{self.media_url}{media_id}/"

        response = self.client.patch(url, {"attribute_value_id": str(self.beige.id)}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(list(ProductMedia.objects.get().attribute_values.all()), [self.beige])

        response = self.client.patch(url, {"attribute_value_id": None}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(ProductMedia.objects.get().attribute_values.exists())

    def test_patch_without_field_keeps_tag(self):
        media_id = self._upload(attribute_value_id=str(self.violet.id)).data["data"]["id"]
        self.client.patch(f"{self.media_url}{media_id}/", {"alt_text": "Violet kada"}, format="json")
        self.assertEqual(list(ProductMedia.objects.get().attribute_values.all()), [self.violet])

    def test_deleting_option_keeps_photo(self):
        self._upload(attribute_value_id=str(self.beige.id))
        self.beige.delete()
        media = ProductMedia.objects.get()
        self.assertFalse(media.attribute_values.exists())

    def test_public_product_data_carries_tag(self):
        self._upload(attribute_value_id=str(self.violet.id))
        self.client.force_authenticate(user=None)
        response = self.client.get(f"/api/v1/catalog/products/slug/{self.product.slug}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        media = response.data["data"]["media"]
        self.assertEqual([str(i) for i in media[0]["attribute_values"]], [str(self.violet.id)])
        self.assertEqual(str(media[0]["attribute_value"]), str(self.violet.id))

    # ── Combinations ───────────────────────────────────────────

    def _tags(self):
        return {str(v.id) for v in ProductMedia.objects.get().attribute_values.all()}

    def test_upload_with_combination(self):
        response = self.client.post(
            self.media_url,
            {"image": make_image_file("p.jpg"), "attribute_value_ids": [str(self.violet.id), str(self.s26.id)]},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(self._tags(), {str(self.violet.id), str(self.s26.id)})
        self.assertEqual(
            {str(i) for i in response.data["data"]["attribute_values"]},
            {str(self.violet.id), str(self.s26.id)},
        )

    def test_comma_separated_ids_accepted(self):
        response = self._upload(attribute_value_ids=f"{self.violet.id},{self.s26.id}")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(self._tags(), {str(self.violet.id), str(self.s26.id)})

    def test_two_options_of_one_attribute_refused(self):
        response = self.client.post(
            self.media_url,
            {"image": make_image_file("p.jpg"), "attribute_value_ids": [str(self.violet.id), str(self.beige.id)]},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(ProductMedia.objects.exists())

    def test_patch_sets_and_clears_combination(self):
        media_id = self._upload().data["data"]["id"]
        url = f"{self.media_url}{media_id}/"
        response = self.client.patch(url, {"attribute_value_ids": [str(self.beige.id), str(self.s26.id)]}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(self._tags(), {str(self.beige.id), str(self.s26.id)})
        response = self.client.patch(url, {"attribute_value_ids": []}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._tags(), set())

    def test_bad_patch_changes_nothing(self):
        media_id = self._upload(attribute_value_id=str(self.violet.id)).data["data"]["id"]
        response = self.client.patch(
            f"{self.media_url}{media_id}/",
            {"alt_text": "changed", "attribute_value_ids": [str(self.foreign_value.id)]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        media = ProductMedia.objects.get()
        self.assertNotEqual(media.alt_text, "changed")
        self.assertEqual(self._tags(), {str(self.violet.id)})
