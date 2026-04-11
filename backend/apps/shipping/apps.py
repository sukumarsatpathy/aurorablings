from django.apps import AppConfig


class ShippingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.shipping"
    verbose_name = "Shipping"

    def ready(self):
        from .providers.registry import registry
        from .providers.local_delivery import LocalDeliveryProvider
        from .providers.nimbuspost import NimbusPostProvider
        from .providers.shiprocket import ShiprocketProvider

        if not registry.is_registered("shiprocket"):
            registry.register(ShiprocketProvider())
        if not registry.is_registered("nimbuspost"):
            registry.register(NimbusPostProvider())
        if not registry.is_registered("local_delivery"):
            registry.register(LocalDeliveryProvider())
