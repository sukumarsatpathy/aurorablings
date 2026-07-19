from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from core.media import delete_file_if_exists
from .models import PromoBanner
from .tasks import invalidate_promo_banner_cache

# Every image field on PromoBanner. Both cleanup receivers below iterate this,
# so a new derivative format only has to be added in one place. Missing a field
# here leaks orphaned files into MEDIA_ROOT on every replace and delete.
BANNER_IMAGE_FIELDS = (
    "image",
    "image_small",
    "image_medium",
    "image_large",
    "image_avif_small",
    "image_avif_medium",
    "image_avif_large",
)

@receiver([post_save, post_delete], sender=PromoBanner)
def handle_promo_banner_change(sender, instance, **kwargs):
    """
    Triggers cache invalidation when a PromoBanner is saved or deleted.
    """
    try:
        invalidate_promo_banner_cache.delay()
    except Exception:
        # If Celery or Redis is down, we don't want to crash the whole request.
        # The cache will just expire naturally or be cleared next time.
        pass


@receiver(pre_save, sender=PromoBanner)
def cleanup_replaced_banner_image(sender, instance, **kwargs):
    if not instance.pk:
        return
    try:
        old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    for field_name in BANNER_IMAGE_FIELDS:
        old_name = getattr(getattr(old, field_name, None), "name", "")
        new_name = getattr(getattr(instance, field_name, None), "name", "")
        if old_name and old_name != new_name:
            delete_file_if_exists(old_name)


@receiver(post_delete, sender=PromoBanner)
def cleanup_deleted_banner_image(sender, instance, **kwargs):
    for field_name in BANNER_IMAGE_FIELDS:
        delete_file_if_exists(getattr(instance, field_name, None))
