from django.conf import settings
from django.db import models


class ConsentStatus(models.TextChoices):
    ACCEPTED_ALL = "accepted_all", "Accepted all"
    REJECTED_ALL = "rejected_all", "Rejected all"
    CUSTOMIZED = "customized", "Customized"


class ConsentSource(models.TextChoices):
    BANNER = "banner", "Banner"
    SETTINGS_MODAL = "settings_modal", "Settings modal"


class CookieConsentLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cookie_consent_logs",
    )
    anonymous_id = models.CharField(max_length=128)
    session_id = models.CharField(max_length=128, blank=True, default="")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")

    consent_status = models.CharField(max_length=32, choices=ConsentStatus.choices)
    consent_version = models.CharField(max_length=32, default="1.0")

    category_necessary = models.BooleanField(default=True)
    category_analytics = models.BooleanField(default=False)
    category_marketing = models.BooleanField(default=False)
    category_preferences = models.BooleanField(default=False)

    source = models.CharField(max_length=32, choices=ConsentSource.choices)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["anonymous_id"]),
            models.Index(fields=["consent_status"]),
        ]

    def __str__(self) -> str:
        return f"CookieConsentLog(id={self.id}, status={self.consent_status}, anonymous_id={self.anonymous_id})"
