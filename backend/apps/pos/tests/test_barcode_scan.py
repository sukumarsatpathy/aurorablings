"""
Barcodes: assigned once, scanned at the till.

What matters: every variant gets an 8-digit number on creation, distinct from
every other and never changed by later edits; staff can't write it; the public
product page doesn't carry it; and a scan at the counter lands on exactly one
sellable variant — or fails loudly rather than adding something close.
"""

from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User, UserRole
from apps.catalog.barcodes import default_label_name, is_barcode
from apps.catalog.models import Attribute, AttributeValue, Category, Product, ProductVariant, VariantAttributeValue


class BarcodeAssignmentTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Earrings", slug="earrings")
        self.product = Product.objects.create(name="Jhumka", slug="jhumka", category=self.category)

    def make(self, sku):
        return ProductVariant.objects.create(product=self.product, sku=sku, price=Decimal("499"))

    def test_new_variants_get_distinct_8_digit_numbers(self):
        a, b = self.make("J-1"), self.make("J-2")
        self.assertTrue(is_barcode(a.barcode), a.barcode)
        self.assertTrue(is_barcode(b.barcode), b.barcode)
        self.assertNotEqual(a.barcode, b.barcode)

    def test_the_number_survives_edits(self):
        a = self.make("J-1")
        original = a.barcode
        a.price = Decimal("549")
        a.save()
        a.save(update_fields=["price"])
        a.refresh_from_db()
        self.assertEqual(a.barcode, original)

    def test_the_api_cannot_overwrite_it(self):
        staff = User.objects.create_user(
            email="s@aurorablings.com", password="x", first_name="S", last_name="S", role=UserRole.ADMIN,
        )
        client = APIClient()
        client.force_authenticate(staff)
        a = self.make("J-1")
        original = a.barcode

        response = client.patch(
            f"/api/v1/catalog/variants/{a.id}/",
            {"barcode": "12345678", "label_name": "Jhumka Red L"},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        a.refresh_from_db()
        self.assertEqual(a.barcode, original)
        self.assertEqual(a.label_name, "Jhumka Red L")
        self.assertEqual(response.data["data"]["barcode"], original)

    def test_public_product_page_does_not_carry_label_fields(self):
        self.product.is_active = True
        self.product.save()
        self.make("J-1")
        response = APIClient().get(f"/api/v1/catalog/products/slug/{self.product.slug}/")
        self.assertEqual(response.status_code, 200, response.data)
        variant = response.data["data"]["variants"][0]
        self.assertNotIn("barcode", variant)
        self.assertNotIn("label_text", variant)


class LabelNameTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name="Necklaces", slug="necklaces")
        self.product = Product.objects.create(name="Kundan Choker Necklace", slug="kc", category=category)
        colour = Attribute.objects.create(product=self.product, name="Color", sort_order=0)
        size = Attribute.objects.create(product=self.product, name="Size", sort_order=1)
        self.green = AttributeValue.objects.create(attribute=colour, value="Green")
        self.large = AttributeValue.objects.create(attribute=size, value="Large")

    def variant(self, *values):
        v = ProductVariant.objects.create(product=self.product, sku=f"KC-{len(values)}", price=Decimal("999"))
        for av in values:
            VariantAttributeValue.objects.create(variant=v, attribute_value=av)
        return v

    def test_options_are_kept_and_the_name_gives_way(self):
        v = self.variant(self.green, self.large)
        name = default_label_name(v)
        self.assertLessEqual(len(name), 20)
        self.assertTrue(name.endswith("Grn L"), name)
        self.assertTrue(name.startswith("Kundan"), name)

    def test_no_options_uses_the_product_name_cut_at_a_word(self):
        v = self.variant()
        self.assertEqual(default_label_name(v), "Kundan Choker")

    def test_an_override_wins(self):
        v = self.variant(self.green)
        v.label_name = "Choker Green"
        self.assertEqual(v.label_text, "Choker Green")


class ScanLookupTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.staff = User.objects.create_user(
            email="priya@aurorablings.com", password="x", first_name="P", last_name="S",
            role=UserRole.STAFF,
        )
        self.client.force_authenticate(self.staff)
        self.category = Category.objects.create(name="Rings", slug="rings")
        self.ring = Product.objects.create(
            name="Oxidised Ring", slug="ox-ring", category=self.category, is_active=True, stock_id=77,
        )
        self.variant = ProductVariant.objects.create(
            product=self.ring, sku="OX-ADJ", price=Decimal("299"), stock_quantity=4, is_active=True,
        )

    def scan(self, code):
        return self.client.get(reverse("pos:scan"), {"code": code})

    def test_a_label_barcode_returns_the_catalogue_row(self):
        response = self.scan(self.variant.barcode)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["variant_id"], str(self.variant.id))
        self.assertEqual(response.data["barcode"], self.variant.barcode)
        self.assertEqual(response.data["price"], "299.00")
        self.assertEqual(response.data["stock"], 4)

    def test_sku_and_single_variant_stock_id_also_work(self):
        self.assertEqual(self.scan("ox-adj").data["variant_id"], str(self.variant.id))
        self.assertEqual(self.scan("77").data["variant_id"], str(self.variant.id))

    def test_a_stock_id_with_several_variations_asks_rather_than_guesses(self):
        ProductVariant.objects.create(product=self.ring, sku="OX-L", price=Decimal("299"), is_active=True)
        response = self.scan("77")
        self.assertEqual(response.status_code, 409, response.data)

    def test_unknown_and_truncated_codes_are_404(self):
        self.assertEqual(self.scan("99999999").status_code, 404)
        # A digit dropped over Bluetooth must not land on another product.
        self.assertEqual(self.scan(self.variant.barcode[:-1]).status_code, 404)

    def test_deleted_or_inactive_products_do_not_scan(self):
        from django.utils import timezone

        self.ring.deleted_at = timezone.now()
        self.ring.save(update_fields=["deleted_at"])
        self.assertEqual(self.scan(self.variant.barcode).status_code, 404)

    def test_catalogue_search_finds_a_barcode(self):
        response = self.client.get(reverse("pos:catalogue"), {"q": self.variant.barcode})
        self.assertEqual([r["sku"] for r in response.data], ["OX-ADJ"])

    def test_customers_cannot_scan(self):
        customer = User.objects.create_user(
            email="c@example.com", password="x", first_name="C", last_name="C", role=UserRole.CUSTOMER,
        )
        self.client.force_authenticate(customer)
        self.assertEqual(self.scan(self.variant.barcode).status_code, 403)
