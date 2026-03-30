import uuid
from django.db import models
from django.utils import timezone


# ─────────────────────────────────────────────────────────────
#  Manager: filters out soft-deleted records by default
# ─────────────────────────────────────────────────────────────
class ActiveManager(models.Manager):
    """Default manager — excludes soft-deleted records."""

    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class AllObjectsManager(models.Manager):
    """Unfiltered manager — includes soft-deleted records."""

    def get_queryset(self):
        return super().get_queryset()


# ─────────────────────────────────────────────────────────────
#  Base Model: UUID primary key + auto timestamps
# ─────────────────────────────────────────────────────────────
class BaseModel(models.Model):
    """
    Abstract base for every model in Aurora Blings.

    Fields:
        id          – UUID4 primary key (non-sequential, safe to expose)
        created_at  – Set once on creation, never updated
        updated_at  – Auto-updated on every save
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.__class__.__name__}({self.id})"


# ─────────────────────────────────────────────────────────────
#  Soft-Delete Model
# ─────────────────────────────────────────────────────────────
class SoftDeleteModel(BaseModel):
    """
    Extends BaseModel with soft-delete behaviour.

    Records are never physically removed — instead `deleted_at`
    is stamped and the default manager filters them out.

    Usage:
        MyModel.objects.all()          # only active records
        MyModel.all_objects.all()      # includes deleted records
        instance.delete()              # soft delete
        instance.hard_delete()         # physical DELETE
        instance.restore()             # undo soft delete
    """

    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    # Replace default manager with soft-delete aware one
    objects = ActiveManager()
    all_objects = AllObjectsManager()

    class Meta:
        abstract = True

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def delete(self, using=None, keep_parents=False):
        """Soft delete: stamp deleted_at instead of removing the row."""
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at"])

    def hard_delete(self):
        """Physical delete — permanently removes the database row."""
        super().delete()

    def restore(self):
        """Undo a soft delete."""
        self.deleted_at = None
        self.save(update_fields=["deleted_at"])
