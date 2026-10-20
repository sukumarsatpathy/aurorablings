"""
Renaming a product's web address.

What matters: the old address keeps opening the product (so shared links and
search results don't break), addresses can't collide, and renaming back and
forth never loops.
"""
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.catalog import services
from apps.catalog.models import Category, Product, ProductSlugRedirect
from core.exceptions import ConflictError, ValidationError


class SlugRedirectTests(TestCase):
    def setUp(self):
        self.category = Category.all_objects.create(name="Bangles", slug="bangles", is_active=True)
        self.product = Product.all_objects.create(
            name="Rose Meher - Set of 2 Bangles", slug="raat-rani-set-of-2-bangles",
            category=self.category, is_active=True,
        )

    def _detail(self, slug):
        return self.client.get(f"/api/v1/catalog/products/slug/{slug}/")

    def test_old_address_still_opens_the_product(self):
        services.rename_product_slug(product=self.product, new_slug="rose-meher-set-of-2-bangles")
        old = self._detail("raat-rani-set-of-2-bangles")
        new = self._detail("rose-meher-set-of-2-bangles")
        self.assertEqual(old.status_code, 200)
        self.assertEqual(old.json()["data"]["slug"], "rose-meher-set-of-2-bangles")
        self.assertEqual(new.status_code, 200)

    def test_new_slug_is_normalised(self):
        services.rename_product_slug(product=self.product, new_slug="Rose Meher Set of 2")
        self.product.refresh_from_db()
        self.assertEqual(self.product.slug, "rose-meher-set-of-2")

    def test_cannot_take_another_products_address(self):
        Product.all_objects.create(name="Laal Noor", slug="laal-noor", category=self.category, is_active=True)
        with self.assertRaises(ConflictError):
            services.rename_product_slug(product=self.product, new_slug="laal-noor")

    def test_cannot_take_another_products_old_address(self):
        other = Product.all_objects.create(name="Laal Noor", slug="laal-noor", category=self.category, is_active=True)
        services.rename_product_slug(product=other, new_slug="laal-noor-set")
        with self.assertRaises(ConflictError):
            services.rename_product_slug(product=self.product, new_slug="laal-noor")

    def test_blank_slug_rejected(self):
        with self.assertRaises(ValidationError):
            services.rename_product_slug(product=self.product, new_slug="!!!")

    def test_renaming_back_drops_the_redirect_and_does_not_loop(self):
        services.rename_product_slug(product=self.product, new_slug="rose-meher")
        services.rename_product_slug(product=self.product, new_slug="raat-rani-set-of-2-bangles")
        self.assertFalse(ProductSlugRedirect.objects.filter(old_slug="raat-rani-set-of-2-bangles").exists())
        self.assertTrue(ProductSlugRedirect.objects.filter(old_slug="rose-meher").exists())
        self.assertEqual(self._detail("rose-meher").json()["data"]["slug"], "raat-rani-set-of-2-bangles")

    def test_unknown_slug_is_still_404(self):
        self.assertEqual(self._detail("no-such-thing").status_code, 404)

    def test_management_command(self):
        out = StringIO()
        call_command("rename_product_slug", "raat-rani-set-of-2-bangles", "rose-meher-set-of-2-bangles", stdout=out)
        self.product.refresh_from_db()
        self.assertEqual(self.product.slug, "rose-meher-set-of-2-bangles")
        self.assertIn("redirects", out.getvalue())
        with self.assertRaises(CommandError):
            call_command("rename_product_slug", "does-not-exist", "x", stdout=StringIO())

    def test_dry_run_changes_nothing(self):
        call_command("rename_product_slug", "raat-rani-set-of-2-bangles", "rose-meher", "--dry-run", stdout=StringIO())
        self.product.refresh_from_db()
        self.assertEqual(self.product.slug, "raat-rani-set-of-2-bangles")
