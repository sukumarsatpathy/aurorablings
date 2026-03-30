from django.apps import AppConfig


class PaymentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.payments"
    verbose_name = "Payments"

    def ready(self):
        # Auto-register all providers on startup
        from apps.payments.providers.registry import registry
        from apps.payments.providers.cashfree import CashfreeProvider
        from apps.payments.providers.razorpay import RazorpayProvider
        from apps.payments.providers.phonepe import PhonePeProvider
        from apps.payments.providers.paypal import PayPalProvider
        from apps.payments.providers.stripe_provider import StripeProvider

        registry.register(CashfreeProvider())
        registry.register(RazorpayProvider())
        registry.register(PhonePeProvider())
        registry.register(PayPalProvider())
        registry.register(StripeProvider())
