"""notifications.selectors"""
from __future__ import annotations
from django.db import models
from django.db.models import QuerySet
from .models import Notification, NotificationTemplate, NotificationLog, NotificationStatus


def get_notifications_for_user(user, *, limit: int = 50) -> QuerySet:
    return (
        Notification.objects
        .filter(user=user)
        .select_related("template")
        .prefetch_related("attempts", "logs")
        .order_by("-created_at")[:limit]
    )


def get_failed_notifications(*, channel: str | None = None, limit: int = 100) -> QuerySet:
    qs = Notification.objects.filter(status=NotificationStatus.FAILED)
    if channel:
        qs = qs.filter(channel=channel)
    return qs.order_by("-created_at")[:limit]


def get_notification_by_id(notif_id) -> Notification | None:
    try:
        return Notification.objects.select_related("template").prefetch_related("logs", "attempts").get(id=notif_id)
    except Notification.DoesNotExist:
        return None


def get_all_notifications(
    *,
    status: str | None = None,
    channel: str | None = None,
    event: str | None = None,
    limit: int = 100,
) -> QuerySet:
    qs = Notification.objects.select_related("user", "template")
    if status:
        qs = qs.filter(status=status)
    if channel:
        qs = qs.filter(channel=channel)
    if event:
        qs = qs.filter(models.Q(event=event) | models.Q(event_type=event))
    return qs.prefetch_related("attempts", "logs").order_by("-created_at")[:limit]


def get_templates() -> QuerySet:
    return NotificationTemplate.objects.all().order_by("event", "channel")
