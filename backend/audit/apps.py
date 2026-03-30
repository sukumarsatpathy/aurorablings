from django.apps import AppConfig


class AuditConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "audit"
    verbose_name = "Audit"

    def ready(self) -> None:
        import audit.signals  # noqa: F401
