"""
Ask NimbusPost which couriers deliver to a pincode, and show its raw answer.

    python manage.py nimbuspost_check 760010
    python manage.py nimbuspost_check 760010 --cod --amount 499 --weight 300

Use it to confirm the login works, and to see whether NimbusPost's answer for
this account includes delivery days (the storefront uses them when present).
"""
import json

from django.core.management.base import BaseCommand, CommandError

from apps.shipping.providers.nimbuspost import NimbusPostProvider


class Command(BaseCommand):
    help = "Check NimbusPost serviceability for a pincode and print the raw response."

    def add_arguments(self, parser):
        parser.add_argument("pincode")
        parser.add_argument("--cod", action="store_true", help="Check cash-on-delivery instead of prepaid.")
        parser.add_argument("--amount", default="499", help="Order amount (needed for COD).")
        parser.add_argument("--weight", type=int, default=None, help="Parcel weight in grams.")

    def handle(self, *args, pincode, cod=False, amount="499", weight=None, **options):
        provider = NimbusPostProvider()
        if not provider.is_configured():
            raise CommandError("Set NIMBUSPOST_EMAIL and NIMBUSPOST_PASSWORD in the server .env first.")
        if not provider.pickup_pincode():
            raise CommandError("Set pickup_pincode in the shipping.nimbuspost setting (admin → Settings).")

        login = provider.authenticate(force=True)
        if not login.success:
            raise CommandError(f"Login failed: {login.error_message}")
        self.stdout.write(self.style.SUCCESS("Login OK."))

        result = provider.check_serviceability(
            destination=pincode, payment_type="cod" if cod else "prepaid", order_amount=amount, weight_grams=weight,
        )
        if not result.success:
            raise CommandError(f"Serviceability check failed: {result.error_message}\n"
                               f"{json.dumps(result.data, indent=2)[:3000]}")

        data = result.data
        self.stdout.write(f"From {provider.pickup_pincode()} to {pincode}: "
                          f"{'SERVICEABLE' if data['serviceable'] else 'NOT serviceable'}")
        for courier in data["couriers"]:
            days = f"{courier['days']} days" if courier["days"] else "no delivery days in response"
            self.stdout.write(f"  - {courier['name']} (id {courier['id']}): ₹{courier['total_charges']} · {days}")
        if data["serviceable"] and not data["days"]:
            self.stdout.write(self.style.WARNING(
                "NimbusPost gave no delivery days, so the product page uses your configured range "
                "(shipping.delivery_estimate min_days/max_days) for serviceable pincodes."
            ))
        self.stdout.write("\nRaw response:")
        self.stdout.write(json.dumps(data["raw"], indent=2, default=str)[:6000])
