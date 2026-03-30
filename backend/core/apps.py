from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "Core"

    def ready(self):
        # Wire up structlog on startup so context vars are initialised.
        import structlog
        structlog.contextvars.clear_contextvars()
