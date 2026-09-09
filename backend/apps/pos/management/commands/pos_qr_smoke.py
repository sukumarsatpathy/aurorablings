"""
Prove the QR path end to end, without touching an order.

check_payment_config says the credentials authenticate and the QR product is
enabled. This asks the next question: does *our* create_qr_code call actually
come back with an image? It raises a ₹1 single-use QR, reports what Razorpay
returned, and closes it again immediately.

No order, no transaction row, no tender — so this is safe to run against any
environment whose keys you are willing to authenticate with.

    python manage.py pos_qr_smoke
"""

from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.payments.providers.registry import registry


class Command(BaseCommand):
    help = "Raise and immediately close a ₹1 test QR, to prove the provider call works."

    def handle(self, *args, **options):
        provider = registry.get("razorpay")
        provider._load_runtime_config()

        if not provider.key_id.startswith("rzp_test"):
            self.stderr.write(self.style.ERROR(
                "These are live keys. Refusing — run this against test keys only."
            ))
            raise SystemExit(1)

        self.stdout.write("Creating a ₹1 single-use QR…")
        result = provider.create_qr_code(
            order_id="smoke-test",
            amount=Decimal("1.00"),
            currency="INR",
            close_by_minutes=5,
            metadata={"channel": "pos", "purpose": "smoke test"},
        )

        if not result.success:
            self.stderr.write(self.style.ERROR(f"  FAILED: {result.error}"))
            if result.raw:
                self.stderr.write(f"  raw: {result.raw}")
            raise SystemExit(1)

        self.stdout.write(self.style.SUCCESS("  Razorpay accepted it."))
        self.stdout.write(f"  qr id:     {result.provider_ref}")
        self.stdout.write(f"  image_url: {result.image_url or '(EMPTY — this is the bug)'}")
        self.stdout.write(f"  close_by:  {result.close_by}")

        if not result.image_url:
            self.stderr.write(self.style.ERROR(
                "\n  The QR was created but carries no image_url, so the counter has "
                "nothing to draw. That is a response-shape problem, not a credentials one."
            ))

        closed = provider.close_qr_code(provider_ref=result.provider_ref)
        self.stdout.write(f"  closed again: {closed}")

        if result.image_url:
            self.stdout.write(self.style.SUCCESS(
                "\nThe provider call works. If the till still shows no code, the problem is "
                "between the endpoint and the screen — check the browser's Network tab for "
                "the POST to /pos/orders/<id>/upi/."
            ))
