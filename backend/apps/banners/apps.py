from django.apps import AppConfig

class BannersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.banners'
    verbose_name = 'Promotional Banners'

    def ready(self):
        import apps.banners.signals
