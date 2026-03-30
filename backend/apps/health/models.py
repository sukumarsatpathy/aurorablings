import uuid

from django.db import models


class HealthSource(models.TextChoices):
    SERVER = "server", "Server"
    API = "api", "API"
    PAYMENT = "payment", "Payment"


class HealthStatus(models.TextChoices):
    HEALTHY = "healthy", "Healthy"
    WARNING = "warning", "Warning"
    DEGRADED = "degraded", "Degraded"
    DOWN = "down", "Down"


class AlertSeverity(models.TextChoices):
    INFO = "info", "Info"
    WARNING = "warning", "Warning"
    CRITICAL = "critical", "Critical"


class HealthCheckResult(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.CharField(max_length=20, choices=HealthSource.choices)
    component = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=HealthStatus.choices)
    response_time_ms = models.IntegerField(null=True, blank=True)
    message = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    checked_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "health check result"
        verbose_name_plural = "health check results"
        ordering = ["-checked_at"]
        indexes = [
            models.Index(fields=["source", "component", "checked_at"]),
            models.Index(fields=["status"]),
            models.Index(fields=["component"]),
        ]

    def __str__(self) -> str:
        return f"{self.component} [{self.source}] - {self.status}"


class HealthAlert(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    component = models.CharField(max_length=255)
    severity = models.CharField(max_length=20, choices=AlertSeverity.choices)
    title = models.CharField(max_length=255)
    message = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "health alert"
        verbose_name_plural = "health alerts"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["component"]),
            models.Index(fields=["is_resolved"]),
        ]

    def __str__(self) -> str:
        return f"{self.severity.upper()}: {self.title}"

