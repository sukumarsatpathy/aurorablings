"""
Each product picks which options of a shared attribute it comes in
(e.g. only Violet and Beige out of seven colours).

What matters: choosing options on one product never changes the shared
attribute or any other product; an option still used by a variant isn't
removed out from under it; a new option typed on a product is added to the
shared list without disturbing the rest.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from apps.catalog import services
from apps.catalog.models import (
    Attribute, AttributeValue, Category, GlobalAttribute, GlobalAttributeOption, Product, ProductVariant,
)

User = get_user_model()

COLOURS = ["Mustard Yellow", "Violet", "Emerald Green", "Malachite Green", "Amber Orange", "Fuchsia", "Beige"]


class ProductAttributeSelectionTests(APITestCase):
    def setUp(self):
        admin = User.objects.create_user(
            email="admin-attr@example.com", password="password123",
            role="admin", is_staff=True, is_superuser=True,
        )
        self.client.force_authenticate(user=admin)
        category = Category.objects.create(name="Bangles", slug="bangles")
        self.colour = services.create_global_attribute(name="Color", options=COLOURS, sort_order=0)
        self.kada = Product.objects.create(name="Noor Kada", slug="noor-kada", category=category, is_active=True)
        self.other = Product.objects.create(name="Laal Kada", slug="laal-kada", category=category, is_active=True)
        services.assign_global_attribute_to_product(product=self.other, global_attribute=self.colour)

    def _url(self, product, attribute_id=None):
        base = f"/api/v1/catalog/products/{product.id}/attributes/"
        return f"{base}{attribute_id}/" if attribute_id else base

    def _values(self, product):
        return list(
            AttributeValue.objects.filter(attribute__product=product, attribute__name="Color")
            .order_by("sort_order").values_list("value", flat=True)
        )

    def _global_active(self):
        return set(GlobalAttributeOption.objects.filter(global_attribute=self.colour, is_active=True).values_list("value", flat=True))

    def test_product_gets_only_chosen_options(self):
        response = self.client.post(
            self._url(self.kada), {"global_attribute_id": str(self.colour.id), "options": ["Beige", "violet"]}, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        # Shared list order and spelling, only the chosen two.
        self.assertEqual(self._values(self.kada), ["Violet", "Beige"])
        self.assertEqual(self._global_active(), set(COLOURS))
        self.assertEqual(len(self._values(self.other)), 7)

    def test_adding_without_options_takes_all(self):
        self.client.post(self._url(self.kada), {"global_attribute_id": str(self.colour.id)}, format="json")
        self.assertEqual(self._values(self.kada), COLOURS)

    def test_removing_an_option_keeps_shared_list_and_other_products(self):
        self.client.post(self._url(self.kada), {"global_attribute_id": str(self.colour.id), "options": ["Violet", "Beige", "Fuchsia"]}, format="json")
        attr = Attribute.objects.get(product=self.kada, name="Color")
        response = self.client.patch(self._url(self.kada, attr.id), {"options": ["Violet", "Beige"]}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(self._values(self.kada), ["Violet", "Beige"])
        self.assertEqual(self._global_active(), set(COLOURS))
        self.assertEqual(len(self._values(self.other)), 7)

    def test_option_used_by_a_variant_is_kept_until_variant_is_gone(self):
        self.client.post(self._url(self.kada), {"global_attribute_id": str(self.colour.id), "options": ["Violet", "Fuchsia"]}, format="json")
        attr = Attribute.objects.get(product=self.kada, name="Color")
        fuchsia = AttributeValue.objects.get(attribute=attr, value="Fuchsia")
        variant = ProductVariant.objects.create(product=self.kada, sku="NK-F", price=Decimal("499"), stock_quantity=1, is_default=True)
        variant.attribute_values.add(fuchsia)

        self.client.patch(self._url(self.kada, attr.id), {"options": ["Violet"]}, format="json")
        self.assertEqual(self._values(self.kada), ["Violet", "Fuchsia"])

        variant.delete()
        self.client.patch(self._url(self.kada, attr.id), {"options": ["Violet"]}, format="json")
        self.assertEqual(self._values(self.kada), ["Violet"])

    def test_new_option_typed_on_product_is_added_to_shared_list(self):
        self.client.post(self._url(self.kada), {"global_attribute_id": str(self.colour.id), "options": ["Violet", "Rose Gold"]}, format="json")
        self.assertEqual(self._values(self.kada), ["Violet", "Rose Gold"])
        self.assertEqual(self._global_active(), set(COLOURS) | {"Rose Gold"})
        self.assertNotIn("Rose Gold", self._values(self.other))

    def test_patch_cannot_rename_shared_attribute(self):
        self.client.post(self._url(self.kada), {"global_attribute_id": str(self.colour.id), "options": ["Violet"]}, format="json")
        attr = Attribute.objects.get(product=self.kada, name="Color")
        self.client.patch(self._url(self.kada, attr.id), {"name": "Shade", "options": ["Violet"]}, format="json")
        self.assertTrue(GlobalAttribute.objects.filter(name="Color").exists())

    def test_editing_shared_list_does_not_add_options_to_products_that_chose(self):
        self.client.post(self._url(self.kada), {"global_attribute_id": str(self.colour.id), "options": ["Violet"]}, format="json")
        services.update_global_attribute(attribute=self.colour, options=COLOURS + ["Black"])
        self.assertEqual(self._values(self.kada), ["Violet"])
