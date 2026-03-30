from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name               = "apps.notifications"
    verbose_name       = "Notifications"

    def ready(self):
        """Register all notification providers on startup."""
        from .providers.registry import registry
        from .providers.email_provider import EmailProvider
        from .providers.whatsapp_provider import WhatsAppProvider
        from .providers.sms_provider import SMSProvider

        registry.register(EmailProvider())
        registry.register(WhatsAppProvider())
        registry.register(SMSProvider())
