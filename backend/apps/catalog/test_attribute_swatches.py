"""
Colour swatches set on the Attributes page.

What matters: a hex code is saved and tidied (#b7410e → #B7410E), bad codes
are refused, a code changed on the Attributes page reaches every product
using that colour (and the product page data), product-only colours keep
their own code, and the swatch switch follows through to products.
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
ATTRS_URL = "/api/v1/catalog/attributes/"


class AttributeSwatchTests(APITestCase):
    def setUp(self):
        admin = User.objects.create_user(
            email="admin-swatch@example.com", password="password123",
            role="admin", is_staff=True, is_superuser=True,
        )
        self.client.force_authenticate(user=admin)
        self.category = Category.objects.create(name="Bangles", slug="bangles")

    def _product(self, slug):
        return Product.objects.create(name=slug.title(), slug=slug, category=self.category, is_active=True)

    def _hex(self, product, value):
        return AttributeValue.objects.get(attribute__product=product, value=value).hex_code

    def test_create_with_colours_and_swatches(self):
        response = self.client.post(ATTRS_URL, {
            "name": "Color",
            "options": ["Rust", "Blush Pink", "Beige"],
            "option_colors": {"Rust": "b7410e", "blush pink": "#f4c2c2"},
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        data = response.data["data"]
        self.assertTrue(data["show_swatches"])  # colour-like name → on by default
        self.assertEqual(data["options"], ["Rust", "Blush Pink", "Beige"])
        self.assertEqual(
            data["option_details"],
            [{"value": "Rust", "hex_code": "#B7410E"}, {"value": "Blush Pink", "hex_code": "#F4C2C2"}, {"value": "Beige", "hex_code": ""}],
        )

    def test_size_is_not_swatches_by_default(self):
        response = self.client.post(ATTRS_URL, {"name": "Size", "options": ["2-4"]}, format="json")
        self.assertFalse(response.data["data"]["show_swatches"])

    def test_bad_code_is_refused_and_nothing_saved(self):
        response = self.client.post(ATTRS_URL, {
            "name": "Color", "options": ["Rust"], "option_colors": {"Rust": "rusty"},
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(GlobalAttribute.objects.filter(name="Color").exists())

    def test_changed_colour_reaches_every_product_and_product_page(self):
        colour = services.create_global_attribute(name="Color", options=["Rust", "Beige"], option_colors={"Rust": "#B7410E"})
        kada, ring = self._product("kada"), self._product("ring")
        for product in (kada, ring):
            services.assign_global_attribute_to_product(product=product, global_attribute=colour, selected=["Rust", "Beige"])
        variant = ProductVariant.objects.create(product=kada, sku="K-R", price=Decimal("499"), stock_quantity=2, is_default=True)
        variant.attribute_values.add(AttributeValue.objects.get(attribute__product=kada, value="Rust"))

        # Only colours sent; options untouched.
        response = self.client.patch(f"{ATTRS_URL}{colour.id}/", {"option_colors": {"Rust": "#A0522D", "Beige": "#E3D3B4"}}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        for product in (kada, ring):
            self.assertEqual(self._hex(product, "Rust"), "#A0522D")
            self.assertEqual(self._hex(product, "Beige"), "#E3D3B4")
        self.assertEqual(
            set(GlobalAttributeOption.objects.filter(global_attribute=colour, is_active=True).values_list("value", flat=True)),
            {"Rust", "Beige"},
        )

        self.client.force_authenticate(user=None)
        page = self.client.get(f"/api/v1/catalog/products/slug/{kada.slug}/").data["data"]
        attr = next(a for a in page["attributes"] if a["name"] == "Color")
        self.assertTrue(attr["show_swatches"])
        self.assertIn({"value": "Rust", "hex_code": "#A0522D"}, [{"value": v["value"], "hex_code": v["hex_code"]} for v in attr["values"]])
        self.assertEqual(page["variants"][0]["attribute_values"][0]["hex_code"], "#A0522D")

    def test_clearing_a_colour(self):
        colour = services.create_global_attribute(name="Color", options=["Rust"], option_colors={"Rust": "#B7410E"})
        self.client.patch(f"{ATTRS_URL}{colour.id}/", {"option_colors": {"Rust": ""}}, format="json")
        self.assertEqual(GlobalAttributeOption.objects.get(global_attribute=colour).hex_code, "")

    def test_saving_options_without_colours_keeps_existing_codes(self):
        colour = services.create_global_attribute(name="Color", options=["Rust"], option_colors={"Rust": "#B7410E"})
        self.client.patch(f"{ATTRS_URL}{colour.id}/", {"options": ["Rust", "Wine"]}, format="json")
        self.assertEqual(GlobalAttributeOption.objects.get(global_attribute=colour, value="Rust").hex_code, "#B7410E")

    def test_swatch_switch_follows_to_products(self):
        colour = services.create_global_attribute(name="Stone shade", options=["Ruby"])
        kada = self._product("kada")
        services.assign_global_attribute_to_product(product=kada, global_attribute=colour)
        self.assertFalse(Attribute.objects.get(product=kada).show_swatches)
        self.client.patch(f"{ATTRS_URL}{colour.id}/", {"show_swatches": True}, format="json")
        self.assertTrue(Attribute.objects.get(product=kada).show_swatches)

    def test_product_only_colour_keeps_blank_code(self):
        colour = services.create_global_attribute(name="Color", options=["Rust"], option_colors={"Rust": "#B7410E"})
        kada = self._product("kada")
        services.assign_global_attribute_to_product(product=kada, global_attribute=colour, selected=["Rust"])
        attr = Attribute.objects.get(product=kada)
        self.client.patch(f"/api/v1/catalog/products/{kada.id}/attributes/{attr.id}/", {"options": ["Rust", "Moss"]}, format="json")
        # "Moss" was typed on the product: added to the shared list without a code.
        self.assertEqual(self._hex(kada, "Moss"), "")
        self.assertEqual(self._hex(kada, "Rust"), "#B7410E")
