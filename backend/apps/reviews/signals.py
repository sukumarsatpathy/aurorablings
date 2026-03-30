from __future__ import annotations

from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver

from core.media import delete_file_if_exists

from .models import ReviewMedia


@receiver(pre_save, sender=ReviewMedia)
def cleanup_replaced_review_media(sender, instance, **kwargs):
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


@receiver(post_delete, sender=ReviewMedia)
def cleanup_deleted_review_media(sender, instance, **kwargs):
    delete_file_if_exists(getattr(instance, "image", None))
