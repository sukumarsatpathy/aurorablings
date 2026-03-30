"""
accounts.signals
~~~~~~~~~~~~~~~~
Post-save / post-delete signal handlers for user lifecycle events.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from core.logging import get_logger
from .models import User

logger = get_logger(__name__)


@receiver(post_save, sender=User)
def on_user_created(sender, instance: User, created: bool, **kwargs):
    if created:
        logger.info(
            "user_created_signal",
            user_id=str(instance.id),
            email=instance.email,
            role=instance.role,
        )
