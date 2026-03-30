from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from core.media import delete_file_if_exists
from .models import PromoBanner
from .tasks import invalidate_promo_banner_cache

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

    old_name = getattr(old.image, "name", "")
    new_name = getattr(instance.image, "name", "")
    if old_name and old_name != new_name:
        delete_file_if_exists(old_name)


@receiver(post_delete, sender=PromoBanner)
def cleanup_deleted_banner_image(sender, instance, **kwargs):
    delete_file_if_exists(getattr(instance, "image", None))
