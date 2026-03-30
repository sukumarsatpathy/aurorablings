from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    verbose_name = "Accounts"

    def ready(self):
        # Import signals to ensure they are registered on startup.
        import apps.accounts.signals  # noqa: F401  # type: ignore
