from django.db import models


class PublishedManager(models.Manager):
    """Only active, non-deleted products."""

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(is_active=True, deleted_at__isnull=True)
        )


class ActiveCategoryManager(models.Manager):
    """Only active (non-hidden) categories."""

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)
