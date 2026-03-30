from __future__ import annotations

from datetime import timedelta

from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone

from ..models import NotificationLog, NotificationLogStatus


def _apply_range(qs, range_key: str | None = None, date_from: str | None = None, date_to: str | None = None):
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)
    if date_from or date_to:
        return qs

    now = timezone.now()
    if range_key == "7d":
        return qs.filter(created_at__gte=now - timedelta(days=7))
    if range_key == "30d":
        return qs.filter(created_at__gte=now - timedelta(days=30))
    if range_key == "90d":
        return qs.filter(created_at__gte=now - timedelta(days=90))
    return qs


def get_notification_stats(range_key: str | None = None, date_from: str | None = None, date_to: str | None = None) -> dict:
    qs = _apply_range(NotificationLog.objects.all(), range_key=range_key, date_from=date_from, date_to=date_to)

    total = qs.count()
    sent = qs.filter(status=NotificationLogStatus.SENT).count()
    failed = qs.filter(status=NotificationLogStatus.FAILED).count()
    pending = qs.filter(status=NotificationLogStatus.PENDING).count()

    success_rate = round((sent / total) * 100, 2) if total else 0.0

    channel_breakdown = list(qs.values("channel").annotate(count=Count("id")).order_by("-count"))
    provider_breakdown = list(qs.values("provider").annotate(count=Count("id")).order_by("-count"))
    top_notification_types = list(qs.values("notification_type").annotate(count=Count("id")).order_by("-count")[:8])

    daily_counts = list(
        qs.annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(total=Count("id"))
        .order_by("day")
    )

    daily_data = []
    for row in daily_counts:
        day = row["day"]
        day_qs = qs.filter(created_at__date=day)
        daily_data.append(
            {
                "day": day.isoformat() if day else "",
                "total": int(row.get("total", 0)),
                "sent": day_qs.filter(status=NotificationLogStatus.SENT).count(),
                "failed": day_qs.filter(status=NotificationLogStatus.FAILED).count(),
            }
        )

    recent_failures = list(
        qs.filter(status=NotificationLogStatus.FAILED)
        .order_by("-created_at")
        .values("id", "recipient", "subject", "provider", "error_message", "created_at")[:8]
    )

    return {
        "total_sent": sent,
        "total_failed": failed,
        "total_pending": pending,
        "success_rate": success_rate,
        "channel_breakdown": channel_breakdown,
        "provider_breakdown": provider_breakdown,
        "top_notification_types": top_notification_types,
        "daily_counts": daily_data,
        "recent_failures": recent_failures,
    }
