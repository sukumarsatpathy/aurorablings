from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class ActorType(models.TextChoices):
    ADMIN = "admin", "Admin"
    STAFF = "staff", "Staff"
    CUSTOMER = "customer", "Customer"
    SYSTEM = "system", "System"
    UNKNOWN = "unknown", "Unknown"


class AuditAction(models.TextChoices):
    CREATE = "CREATE", "Create"
    UPDATE = "UPDATE", "Update"
    DELETE = "DELETE", "Delete"
    LOGIN = "LOGIN", "Login"
    LOGOUT = "LOGOUT", "Logout"
    STATUS_CHANGE = "STATUS_CHANGE", "Status Change"


class ActivityLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="activity_logs",
    )
    actor_type = models.CharField(max_length=20, choices=ActorType.choices, db_index=True)
    action = models.CharField(max_length=20, choices=AuditAction.choices, db_index=True)
    entity_type = models.CharField(max_length=60, db_index=True)
    entity_id = models.CharField(max_length=120, null=True, blank=True, db_index=True)
    description = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.CharField(max_length=64, null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    request_id = models.CharField(max_length=100, null=True, blank=True)
    path = models.CharField(max_length=500, null=True, blank=True)
    method = models.CharField(max_length=16, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["user"]),
            models.Index(fields=["action"]),
            models.Index(fields=["entity_type"]),
            models.Index(fields=["entity_id"]),
            models.Index(fields=["entity_type", "entity_id"]),
            models.Index(fields=["actor_type", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.action} {self.entity_type}:{self.entity_id or '-'}"
