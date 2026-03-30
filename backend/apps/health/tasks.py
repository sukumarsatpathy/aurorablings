"""Celery tasks for health monitoring."""

from __future__ import annotations

from celery import shared_task
from django.db import transaction

from apps.health.alert_engine import HealthAlertEngine
from apps.health.models import HealthCheckResult, HealthSource, HealthStatus
from apps.health.services import APIHealthMonitorService, PaymentHealthService, ServerHealthService
from core.logging import get_logger

logger = get_logger(__name__)


@shared_task(
    bind=True,
    name="health.run_server_health_checks",
    soft_time_limit=50,
    time_limit=55,
    ignore_result=False,
)
def run_server_health_checks(self):
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
    return _run_health_pipeline(
        source=HealthSource.PAYMENT,
        service=PaymentHealthService(),
    )


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
