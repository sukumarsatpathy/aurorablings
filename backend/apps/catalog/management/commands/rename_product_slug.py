"""
Give a product a new web address; the old one keeps working.

    python manage.py rename_product_slug raat-rani-set-of-2-bangles rose-meher-set-of-2-bangles
    python manage.py rename_product_slug raat-rani-set-of-2-bangles rose-meher-set-of-2-bangles --dry-run
"""
from django.core.management.base import BaseCommand, CommandError

from apps.catalog import services
from apps.catalog.models import Product
from core.exceptions import ConflictError, ValidationError


class Command(BaseCommand):
    help = "Rename a product's slug and redirect the old address to it."

    def add_arguments(self, parser):
        parser.add_argument("old_slug")
        parser.add_argument("new_slug")
        parser.add_argument("--dry-run", action="store_true", help="Show what would change without saving.")

    def handle(self, *args, old_slug, new_slug, dry_run=False, **options):
        product = Product.all_objects.filter(slug=old_slug).first()
        if product is None:
            raise CommandError(f"No product has the slug '{old_slug}'.")
        if dry_run:
            self.stdout.write(f"Would rename '{product.name}': {old_slug} → {new_slug} (old address redirects).")
            return
        try:
            services.rename_product_slug(product=product, new_slug=new_slug)
        except (ConflictError, ValidationError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(
            f"'{product.name}' now lives at /product/{product.slug} — /product/{old_slug} redirects there."
        ))
