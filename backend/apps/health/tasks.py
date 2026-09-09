"""Celery tasks for health monitoring."""

from __future__ import annotations

from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.health.alert_engine import HealthAlertEngine
from apps.health.models import HealthCheckResult, HealthSource, HealthStatus
from apps.health.services import APIHealthMonitorService, PaymentHealthService, ServerHealthService
from core.logging import get_logger

logger = get_logger(__name__)


def _collection_enabled() -> bool:
    """Whether the health-monitoring subsystem should collect anything.

    This guard is load-bearing, not belt-and-braces. Beat runs
    django_celery_beat's DatabaseScheduler, which syncs CELERY_BEAT_SCHEDULE
    into PeriodicTask rows but does not delete rows for entries that later
    disappear from settings. Dropping the three health.* entries from the
    schedule therefore does NOT stop an already-created row from firing. This
    check is what actually stops the work.
    """
    return bool(getattr(settings, "HEALTH_MONITORING_ENABLED", False))


def _disabled_result(source: str) -> dict:
    return {"source": source, "skipped": True, "reason": "HEALTH_MONITORING_ENABLED is false"}


@shared_task(
    bind=True,
    name="health.run_server_health_checks",
    soft_time_limit=50,
    time_limit=55,
    ignore_result=False,
)
def run_server_health_checks(self):
    if not _collection_enabled():
        return _disabled_result(HealthSource.SERVER)
    return _run_health_pipeline(
        source=HealthSource.SERVER,
        service=ServerHealthService(),
    )


@shared_task(
    bind=True,
    name="health.run_api_health_checks",
    soft_time_limit=50,
    time_limit=55,
    ignore_result=False,
)
def run_api_health_checks(self):
    if not _collection_enabled():
        return _disabled_result(HealthSource.API)
    return _run_health_pipeline(
        source=HealthSource.API,
        service=APIHealthMonitorService(),
    )


@shared_task(
    bind=True,
    name="health.run_payment_health_checks",
    soft_time_limit=50,
    time_limit=55,
    ignore_result=False,
)
def run_payment_health_checks(self):
    if not _collection_enabled():
        return _disabled_result(HealthSource.PAYMENT)
    return _run_health_pipeline(
        source=HealthSource.PAYMENT,
        service=PaymentHealthService(),
    )


@shared_task(
    bind=True,
    name="health.prune_health_results",
    soft_time_limit=280,
    time_limit=300,
    ignore_result=True,
)
def prune_health_results(self, days: int | None = None) -> dict:
    """Bound the HealthCheckResult table.

    Nothing pruned this table before. The health tasks only ever appended to
    it, so it grew by roughly 13,000 rows a day at the old check intervals --
    each row carrying a TextField and a JSONField, across four indexes. The
    cost is not the storage; it is that autovacuum and the dashboard's
    per-component Subquery both get steadily slower, which reads as production
    CPU that climbs week over week for no visible reason.

    Deletes in batches so a long-overdue first run cannot hold a single
    transaction open across millions of rows.
    """
    retention_days = days if days is not None else getattr(settings, "HEALTH_RESULT_RETENTION_DAYS", 14)
    cutoff = timezone.now() - timedelta(days=int(retention_days))

    deleted_total = 0
    while True:
        batch_ids = list(
            HealthCheckResult.objects.filter(checked_at__lt=cutoff)
            .values_list("id", flat=True)[:5000]
        )
        if not batch_ids:
            break
        deleted, _ = HealthCheckResult.objects.filter(id__in=batch_ids).delete()
        deleted_total += deleted
        if len(batch_ids) < 5000:
            break

    logger.info("health_results_pruned", deleted=deleted_total, retention_days=retention_days)
    return {"deleted": deleted_total, "retention_days": retention_days}


def _run_health_pipeline(*, source: str, service) -> dict:
    try:
        check_payloads = service.check_all()
    except Exception as exc:
        logger.exception(
            "health_service_failed",
            source=source,
            error=str(exc),
            service=service.__class__.__name__,
        )
        check_payloads = [
            {
                "component": f"{source}:service",
                "status": HealthStatus.DOWN,
                "response_time_ms": 0,
                "message": f"Health service failure: {exc}",
                "metadata": {"service": service.__class__.__name__},
            }
        ]

    persisted_results = _persist_results(source=source, payloads=check_payloads)
    alert_stats = HealthAlertEngine.process_results(persisted_results)

    summary = {
        "source": source,
        "checks_run": len(check_payloads),
        "results_persisted": len(persisted_results),
        **alert_stats,
    }
    logger.info("health_checks_completed", **summary)
    return summary


@transaction.atomic
def _persist_results(*, source: str, payloads: list[dict]) -> list[HealthCheckResult]:
    instances: list[HealthCheckResult] = []
    for payload in payloads:
        normalized_status = _normalize_status(payload.get("status"))
        instance = HealthCheckResult(
            source=source,
            component=(payload.get("component") or "unknown").strip()[:255],
            status=normalized_status,
            response_time_ms=_coerce_int(payload.get("response_time_ms")),
            message=(payload.get("message") or f"{source} health check").strip(),
            metadata=payload.get("metadata") or {},
        )
        instances.append(instance)

    HealthCheckResult.objects.bulk_create(instances)
    return instances


def _normalize_status(status: str | None) -> str:
    value = (status or "").lower().strip()
    if value in {
        HealthStatus.HEALTHY,
        HealthStatus.WARNING,
        HealthStatus.DEGRADED,
        HealthStatus.DOWN,
    }:
        return value
    return HealthStatus.DOWN


def _coerce_int(value) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
