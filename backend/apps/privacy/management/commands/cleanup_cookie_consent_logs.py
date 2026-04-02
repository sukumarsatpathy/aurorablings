from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.privacy.models import CookieConsentLog


class Command(BaseCommand):
    help = "Delete cookie consent logs older than configured days"

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=365, help="Delete logs older than N days")

    def handle(self, *args, **options):
        days = int(options["days"])
        cutoff = timezone.now() - timedelta(days=days)
        deleted_count, _ = CookieConsentLog.objects.filter(created_at__lt=cutoff).delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted_count} cookie consent logs older than {days} days."))
