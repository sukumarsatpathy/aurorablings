"""Alerting engine for health-monitoring check results."""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.health.models import AlertSeverity, HealthAlert, HealthCheckResult, HealthStatus


class HealthAlertEngine:
    """Evaluates health results and creates/resolves alerts."""

    SEVERITY_BY_STATUS = {
        HealthStatus.WARNING: AlertSeverity.WARNING,
        HealthStatus.DEGRADED: AlertSeverity.CRITICAL,
        HealthStatus.DOWN: AlertSeverity.CRITICAL,
    }

    @classmethod
    @transaction.atomic
    def process_results(cls, results: list[HealthCheckResult]) -> dict[str, int]:
        created = 0
        resolved = 0

        for result in results:
            if result.status == HealthStatus.HEALTHY:
                resolved += cls._resolve_alerts_for_component(result.component)
                continue

            severity = cls.SEVERITY_BY_STATUS.get(result.status)
            if not severity:
                continue

            exists = HealthAlert.objects.filter(
                component=result.component,
                is_resolved=False,
            ).exists()
            if exists:
                continue

            HealthAlert.objects.create(
                component=result.component,
                severity=severity,
                title=f"{result.component} health is {result.status}",
                message=result.message or "Health degradation detected",
                metadata={
                    "source": result.source,
                    "status": result.status,
                    "response_time_ms": result.response_time_ms,
                    **(result.metadata or {}),
                },
            )
            created += 1

        return {"alerts_created": created, "alerts_resolved": resolved}

    @staticmethod
    def _resolve_alerts_for_component(component: str) -> int:
        qs = HealthAlert.objects.filter(component=component, is_resolved=False)
        updated = qs.update(is_resolved=True, resolved_at=timezone.now())
        return int(updated)
