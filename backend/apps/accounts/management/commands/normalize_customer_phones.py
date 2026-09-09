"""
Rewrite stored phone numbers to bare ten digits.

Counter lookup already matches several stored shapes, but a number saved as
"+91 98765 43210" — with spaces inside it — can only be found by normalising the
data. Running this once makes every lookup exact and cheap, and stops staff
creating a duplicate because the till said "new customer" about a regular.

    python manage.py normalize_customer_phones --dry-run
    python manage.py normalize_customer_phones
"""

from django.core.management.base import BaseCommand

from apps.accounts.customer_linking import phone_digits
from apps.accounts.models import User


class Command(BaseCommand):
    help = "Normalise User.phone to bare 10-digit numbers."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Report only; change nothing.")

    def handle(self, *args, **opts):
        changed, skipped, ambiguous = 0, 0, []

        for user in User.objects.exclude(phone="").only("id", "phone").iterator(chunk_size=500):
            digits = phone_digits(user.phone)

            if len(digits) != 10:
                # Too short or too long to be an Indian mobile. Left alone and
                # reported: guessing at a partial number is worse than leaving it.
                ambiguous.append(f"{user.id}: {user.phone!r}")
                continue

            if user.phone == digits:
                skipped += 1
                continue

            self.stdout.write(f"  {user.phone!r} -> {digits!r}")
            if not opts["dry_run"]:
                user.phone = digits
                user.save(update_fields=["phone"])
            changed += 1

        verb = "would change" if opts["dry_run"] else "changed"
        self.stdout.write(self.style.SUCCESS(f"\n{verb} {changed}; already clean {skipped}."))

        if ambiguous:
            self.stdout.write(self.style.WARNING(f"{len(ambiguous)} left alone (not 10 digits):"))
            for line in ambiguous[:20]:
                self.stdout.write(f"  - {line}")
