from __future__ import annotations

from django.utils import timezone

from apps.features import services as feature_services

from ..models import NotificationLogStatus, NotificationProvider, NotificationProviderSettings
from .senders.brevo_sender import BrevoSender
from .senders.smtp_sender import SMTPSender


PROVIDER_TO_SENDER = {
    NotificationProvider.SMTP: SMTPSender,
    NotificationProvider.BREVO: BrevoSender,
}


def _is_provider_active(provider_type: str) -> bool:
    if provider_type == NotificationProvider.SMTP:
        cfg = feature_services.get_setting("notification.smtp", default={}) or {}
        if not cfg:
            cfg = feature_services.get_setting("email.smtp", default={}) or {}
        return bool(cfg.get("enabled", False))
    if provider_type == NotificationProvider.BREVO:
        cfg = feature_services.get_setting("notification.brevo", default={}) or {}
        return bool(cfg.get("enabled", False))
    return False


def test_provider(provider_settings: NotificationProviderSettings) -> NotificationProviderSettings:
    sender_cls = PROVIDER_TO_SENDER.get(provider_settings.provider_type)
    now = timezone.now()

    if not sender_cls:
        provider_settings.last_tested_at = now
        provider_settings.last_test_status = NotificationLogStatus.FAILED
        provider_settings.last_test_message = "No sender available for this provider"
        provider_settings.save(update_fields=["last_tested_at", "last_test_status", "last_test_message", "updated_at"])
        return provider_settings

    ok, message = sender_cls().test_connection()
    provider_settings.last_tested_at = now
    provider_settings.last_test_status = NotificationLogStatus.SENT if ok else NotificationLogStatus.FAILED
    provider_settings.last_test_message = message
    provider_settings.is_active = _is_provider_active(provider_settings.provider_type)
    provider_settings.save(
        update_fields=["last_tested_at", "last_test_status", "last_test_message", "is_active", "updated_at"]
    )
    return provider_settings


def ensure_default_provider_rows() -> None:
    for provider_type in [NotificationProvider.SMTP, NotificationProvider.BREVO]:
        NotificationProviderSettings.objects.get_or_create(
            provider_type=provider_type,
            defaults={
                "config": {},
                "is_active": _is_provider_active(provider_type),
            },
        )


def get_provider_status_summary() -> list[NotificationProviderSettings]:
    ensure_default_provider_rows()
    rows = list(NotificationProviderSettings.objects.all().order_by("provider_type"))
    updated = []
    for row in rows:
        active = _is_provider_active(row.provider_type)
        if row.is_active != active:
            row.is_active = active
            updated.append(row)
    if updated:
        NotificationProviderSettings.objects.bulk_update(updated, ["is_active", "updated_at"])
        rows = list(NotificationProviderSettings.objects.all().order_by("provider_type"))
    return rows
