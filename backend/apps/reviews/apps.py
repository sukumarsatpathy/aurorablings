from django.apps import AppConfig


class ReviewsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.reviews"
    verbose_name = "Reviews"

    def ready(self):
        import apps.reviews.signals  # noqa: F401  # type: ignore
