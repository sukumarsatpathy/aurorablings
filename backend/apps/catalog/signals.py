from __future__ import annotations

from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver

from core.media import delete_file_if_exists

from .models import Brand, Category, ProductMedia


def _cleanup_replaced_file(sender, instance, field_name: str):
    if not instance.pk:
        return
    try:
        old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    old_file = getattr(old, field_name, None)
    new_file = getattr(instance, field_name, None)
    old_name = getattr(old_file, "name", "")
    new_name = getattr(new_file, "name", "")
    if old_name and old_name != new_name:
        delete_file_if_exists(old_name)


@receiver(pre_save, sender=Category)
def cleanup_replaced_category_image(sender, instance, **kwargs):
    _cleanup_replaced_file(sender, instance, "image")


@receiver(post_delete, sender=Category)
def cleanup_deleted_category_image(sender, instance, **kwargs):
    delete_file_if_exists(getattr(instance, "image", None))


@receiver(pre_save, sender=Brand)
def cleanup_replaced_brand_logo(sender, instance, **kwargs):
    _cleanup_replaced_file(sender, instance, "logo")


@receiver(post_delete, sender=Brand)
def cleanup_deleted_brand_logo(sender, instance, **kwargs):
    delete_file_if_exists(getattr(instance, "logo", None))


@receiver(pre_save, sender=ProductMedia)
def cleanup_replaced_product_media(sender, instance, **kwargs):
    _cleanup_replaced_file(sender, instance, "image")
    _cleanup_replaced_file(sender, instance, "image_small")
    _cleanup_replaced_file(sender, instance, "image_medium")
    _cleanup_replaced_file(sender, instance, "image_large")


@receiver(post_delete, sender=ProductMedia)
def cleanup_deleted_product_media(sender, instance, **kwargs):
    delete_file_if_exists(getattr(instance, "image", None))
    delete_file_if_exists(getattr(instance, "image_small", None))
    delete_file_if_exists(getattr(instance, "image_medium", None))
    delete_file_if_exists(getattr(instance, "image_large", None))
