from __future__ import annotations

from django.conf import settings
from django.utils import timezone

from core.logging import get_logger

from ..models import NotificationLog, NotificationLogStatus, NotificationStatus
from .notification_service import send_notification

logger = get_logger(__name__)


MAX_RETRY = int(getattr(settings, "NOTIFICATION_MAX_RETRY", 3))


def can_retry(log: NotificationLog) -> bool:
    return log.status == NotificationLogStatus.FAILED and log.attempts_count < MAX_RETRY and bool(log.notification_id)


def increment_attempts(log: NotificationLog) -> NotificationLog:
    log.attempts_count = int(log.attempts_count or 0) + 1
    log.last_attempt_at = timezone.now()
    log.status = NotificationLogStatus.RETRYING
    log.save(update_fields=["attempts_count", "last_attempt_at", "status"])
    return log


def retry_notification(log_id: str) -> NotificationLog:
    log = NotificationLog.objects.select_related("notification").filter(id=log_id).first()
    if not log:
        raise ValueError("Notification log not found")

    if not can_retry(log):
        raise ValueError("This notification cannot be retried")

    increment_attempts(log)

    notification = log.notification
    notification.status = NotificationStatus.PENDING
    notification.save(update_fields=["status", "updated_at"])

    send_notification(notification_id=str(notification.id))

    latest = NotificationLog.objects.filter(notification=notification).order_by("-created_at").first()
    if latest:
        logger.info("notification_retry_completed", log_id=str(log.id), latest_log_id=str(latest.id))
        return latest
    return log
