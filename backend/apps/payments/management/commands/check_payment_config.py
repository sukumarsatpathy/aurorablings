"""
Where are the gateway credentials coming from, and do they work?

Credentials can arrive from two places — Django settings (that is, the
environment) and an AppSetting / ProviderConfig row in the database — with the
database winning. When a key is missing, the counter's only symptom is a QR
button that 409s, which says nothing about which of the two places to go and
fix. This says it.

Secrets are never printed. Only whether something is set, how long it is, and
its first four characters, which is enough to spot a truncated paste or a live
key where a test key was intended.

    python manage.py check_payment_config
    python manage.py check_payment_config --probe    # calls Razorpay
"""

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.payments.providers.registry import registry


def _fingerprint(value: str) -> str:
    if not value:
        return "not set"
    return f"set ({len(value)} chars, starts {value[:4]}…)"


class Command(BaseCommand):
    help = "Report where Razorpay credentials resolve from, without printing them."

    def add_arguments(self, parser):
        parser.add_argument(
            "--probe",
            action="store_true",
            help="Make a real call to Razorpay to prove the credentials are accepted.",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("Django settings (from the environment)"))
        for name in ("RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET", "RAZORPAY_WEBHOOK_SECRET"):
            defined = hasattr(settings, name)
            value = str(getattr(settings, name, "") or "")
            if not defined:
                self.stdout.write(f"  {name}: NOT DEFINED as a setting — the environment is ignored")
            else:
                self.stdout.write(f"  {name}: {_fingerprint(value)}")

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Database rows"))
        self._report_db()

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("What the provider actually resolved"))
        try:
            provider = registry.get("razorpay")
        except KeyError as exc:
            self.stderr.write(self.style.ERROR(f"  razorpay is not registered: {exc}"))
            raise SystemExit(1)

        provider._load_runtime_config()
        self.stdout.write(f"  key_id:         {_fingerprint(provider.key_id)}")
        self.stdout.write(f"  key_secret:     {_fingerprint(provider.key_secret)}")
        self.stdout.write(f"  webhook_secret: {_fingerprint(provider.webhook_secret)}")

        if not provider.key_id or not provider.key_secret:
            self.stderr.write(self.style.ERROR(
                "\n  No usable credentials. Set them in the admin (an AppSetting keyed "
                "'payment.razorpay' with key_id/key_secret, or an active razorpay "
                "ProviderConfig under a payment feature), or as RAZORPAY_KEY_ID / "
                "RAZORPAY_KEY_SECRET in the environment."
            ))
            raise SystemExit(1)

        mode = "TEST" if provider.key_id.startswith("rzp_test") else "LIVE"
        self.stdout.write(f"  mode:           {mode}")
        if mode == "LIVE":
            self.stdout.write(self.style.WARNING("  These are live keys. Real money."))

        if not options["probe"]:
            self.stdout.write(self.style.SUCCESS("\nCredentials resolve. Re-run with --probe to prove Razorpay accepts them."))
            return

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Probe"))
        self._probe(provider)

    def _report_db(self):
        try:
            from apps.features.models import AppSetting, ProviderConfig
        except Exception as exc:  # noqa: BLE001
            self.stdout.write(f"  features app unavailable: {exc}")
            return

        keys = ["payment.razorpay", "payment-razorpay", "payment_razorpay", "razorpay"]
        setting = AppSetting.objects.filter(key__in=keys).order_by("-updated_at").first()
        if setting:
            value = setting.typed_value
            fields = sorted(value.keys()) if isinstance(value, dict) else f"not a dict ({type(value).__name__})"
            self.stdout.write(f"  AppSetting '{setting.key}': {fields}")
        else:
            other = AppSetting.objects.filter(key__icontains="razorpay").values_list("key", flat=True)
            if other:
                self.stdout.write(self.style.WARNING(
                    f"  No AppSetting with a recognised key. Found: {list(other)}. "
                    f"The provider only reads one of {keys}."
                ))
            else:
                self.stdout.write("  AppSetting: none")

        row = ProviderConfig.objects.filter(provider_key="razorpay").order_by("-updated_at").first()
        if row:
            usable = row.is_active and getattr(row.feature, "category", "") == "payment"
            note = "" if usable else "  ← ignored: needs is_active and a feature in the 'payment' category"
            fields = sorted(row.config.keys()) if isinstance(row.config, dict) else "not a dict"
            self.stdout.write(
                f"  ProviderConfig: active={row.is_active} "
                f"category={getattr(row.feature, 'category', '?')} fields={fields}{note}"
            )
        else:
            self.stdout.write("  ProviderConfig: none")

    def _probe(self, provider):
        """One cheap authenticated GET, then the QR product specifically."""
        import requests

        auth = (provider.key_id, provider.key_secret)
        try:
            response = requests.get(
                f"{provider.base_url}/payments?count=1", auth=auth, timeout=15,
            )
        except Exception as exc:  # noqa: BLE001
            self.stderr.write(self.style.ERROR(f"  Could not reach Razorpay: {exc}"))
            raise SystemExit(1)

        if response.status_code == 401:
            self.stderr.write(self.style.ERROR("  401 — Razorpay rejected the key/secret pair."))
            raise SystemExit(1)
        if response.status_code >= 400:
            self.stderr.write(self.style.ERROR(f"  {response.status_code} — {response.text[:300]}"))
            raise SystemExit(1)
        self.stdout.write(self.style.SUCCESS("  Authentication accepted."))

        # The QR Codes API is a separate product and is not on by default. A POS
        # that falls back to payment links for every sale is usually this.
        qr = requests.get(f"{provider.base_url}/payments/qr_codes?count=1", auth=auth, timeout=15)
        if qr.status_code < 400:
            self.stdout.write(self.style.SUCCESS("  QR Codes API is enabled on this account."))
        else:
            self.stdout.write(self.style.WARNING(
                f"  QR Codes API unavailable ({qr.status_code}): {qr.text[:200]}\n"
                "  The counter will fall back to payment links rendered as QR codes."
            ))
