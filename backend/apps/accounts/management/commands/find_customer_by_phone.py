"""
Ask the same question the counter asks, from the shell.

When the till says "no account on this number" and you believe otherwise, this
shows every place the number could be hiding and what the lookup concluded — so
the answer is a fact rather than a guess.

    python manage.py find_customer_by_phone 9876543210
"""

from django.core.management.base import BaseCommand

from apps.accounts.customer_linking import find_customer, phone_digits, phone_query
from apps.accounts.models import Address, User
from apps.orders.models import Order


class Command(BaseCommand):
    help = "Diagnose customer lookup for one phone number."

    def add_arguments(self, parser):
        parser.add_argument("phone")

    def handle(self, *args, **opts):
        raw = opts["phone"]
        digits = phone_digits(raw)
        self.stdout.write(f"Typed {raw!r} → matching on {digits!r}\n")

        users = User.objects.filter(phone_query(raw))
        self.stdout.write(self.style.MIGRATE_HEADING("User.phone matches"))
        for u in users[:10]:
            self.stdout.write(f"  {u.email}  phone={u.phone!r}  role={u.role}  active={u.is_active}")
        if not users.exists():
            self.stdout.write("  (none)")

        addresses = Address.objects.filter(phone_query(raw)).select_related("user")
        self.stdout.write(self.style.MIGRATE_HEADING("Address.phone matches"))
        for a in addresses[:10]:
            owner = a.user.email if a.user_id else "(no user)"
            self.stdout.write(f"  {owner}  phone={a.phone!r}  {a.city}")
        if not addresses.exists():
            self.stdout.write("  (none)")

        orders = Order.objects.filter(contact_phone__endswith=digits) if digits else Order.objects.none()
        self.stdout.write(self.style.MIGRATE_HEADING("Counter orders with this contact number"))
        self.stdout.write(f"  {orders.count()}")

        result = find_customer(phone=raw)
        self.stdout.write(self.style.MIGRATE_HEADING("What the counter would say"))
        if result.user:
            self.stdout.write(self.style.SUCCESS(
                f"  found: {result.user.email} ({result.reason})"
            ))
        elif result.conflict:
            self.stdout.write(self.style.WARNING(f"  conflict: {result.reason}"))
        else:
            self.stdout.write(self.style.WARNING(f"  not found: {result.reason}"))

        # The most common reason a known customer looks like a stranger.
        non_customers = User.objects.filter(phone_query(raw)).exclude(role="customer")
        if non_customers.exists() and not result.user:
            self.stdout.write(self.style.ERROR(
                "\n  Note: this number belongs to a non-customer account "
                f"({', '.join(u.role for u in non_customers[:3])}). "
                "Lookup only matches role=customer."
            ))
