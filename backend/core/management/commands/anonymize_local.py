"""
Scrub customer PII from a database restored from production.

This is a DESTRUCTIVE, LOCAL-ONLY command. It refuses to run unless the
configured database host looks like a local one, so it cannot be pointed at
production by accident.

    python manage.py anonymize_local --yes
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "db", ""}

# Every customer account gets this password, so you can log in as anyone.
LOCAL_PASSWORD = "localdev123"


class Command(BaseCommand):
    help = "Replace customer PII with fake values. Local development only."

    def add_arguments(self, parser):
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Skip the interactive confirmation prompt.",
        )

    # ── Safety ───────────────────────────────────────────────────
    def _assert_local(self):
        db = settings.DATABASES["default"]
        host = (db.get("HOST") or "").strip()

        if host not in LOCAL_HOSTS:
            raise CommandError(
                f"Refusing to run: database host is '{host}', which is not a "
                f"recognised local host. This command is destructive and must "
                f"never run against production."
            )

        allowed = set(getattr(settings, "ALLOWED_HOSTS", []))
        if "aurorablings.com" in allowed or "www.aurorablings.com" in allowed:
            raise CommandError(
                "Refusing to run: ALLOWED_HOSTS contains the production domain. "
                "This looks like a production settings module."
            )

    def handle(self, *args, **options):
        self._assert_local()

        if not options["yes"]:
            self.stdout.write(self.style.WARNING(
                "This will permanently overwrite customer data in the local database."
            ))
            if input("Continue? [y/N] ").strip().lower() != "y":
                raise CommandError("Aborted.")

        from django.contrib.auth.hashers import make_password

        from apps.accounts.models import Address, LoginAttempt, User
        from apps.catalog.models import ProductStockNotifyRequest
        from apps.notifications.models import (
            ContactQuery,
            EmailLog,
            NewsletterSubscriber,
            Notification,
            NotificationAttempt,
            NotificationLog,
            NotifySubscription,
        )
        from apps.orders.models import Order

        hashed = make_password(LOCAL_PASSWORD)

        with transaction.atomic():
            # ── Users ────────────────────────────────────────────
            # Staff and admin accounts keep their emails so you can still
            # log in to the admin; only their personal details are reset.
            count = 0
            for user in User.objects.all().iterator():
                is_privileged = user.is_superuser or user.role in ("admin", "staff")
                if not is_privileged:
                    user.email = f"customer{count}@example.invalid"
                user.first_name = "Test"
                user.last_name = f"User{count}"
                user.phone = "9000000000"
                user.password = hashed
                user.password_reset_token = ""
                user.password_reset_expires = None
                user.save(update_fields=[
                    "email", "first_name", "last_name", "phone",
                    "password", "password_reset_token", "password_reset_expires",
                ])
                count += 1
            self.stdout.write(f"  users anonymized:        {count}")

            # ── Saved addresses ──────────────────────────────────
            n = 0
            for addr in Address.objects.all().iterator():
                addr.full_name = "Test User"
                addr.line1 = "1 Test Street"
                addr.line2 = ""
                addr.postal_code = "400001"
                addr.phone = "9000000000"
                addr.save(update_fields=[
                    "full_name", "line1", "line2", "postal_code", "phone",
                ])
                n += 1
            self.stdout.write(f"  addresses anonymized:    {n}")

            # ── Order address snapshots ──────────────────────────
            fake_addr = {
                "full_name": "Test User",
                "line1": "1 Test Street",
                "line2": "",
                "city": "Mumbai",
                "state": "Maharashtra",
                "postal_code": "400001",
                "country": "India",
                "phone": "9000000000",
            }
            n = 0
            for order in Order.objects.all().iterator():
                if order.guest_email:
                    order.guest_email = f"guest{n}@example.invalid"
                if order.shipping_address:
                    order.shipping_address = dict(fake_addr)
                if order.billing_address:
                    order.billing_address = dict(fake_addr)
                order.save(update_fields=[
                    "guest_email", "shipping_address", "billing_address",
                ])
                n += 1
            self.stdout.write(f"  orders scrubbed:         {n}")

            # ── Transient logs: no dev value, all PII ────────────
            wiped = []
            for model in (
                LoginAttempt,
                Notification,
                NotificationAttempt,
                NotificationLog,
                NotifySubscription,
                NewsletterSubscriber,
                ContactQuery,
                EmailLog,
                ProductStockNotifyRequest,
            ):
                deleted, _ = model.objects.all().delete()
                wiped.append(f"{model.__name__}={deleted}")
            self.stdout.write("  log tables cleared:      " + ", ".join(wiped))

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. Every customer account now uses the password '{LOCAL_PASSWORD}'."
        ))
