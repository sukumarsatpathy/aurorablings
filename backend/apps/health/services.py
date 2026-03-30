"""Health monitoring services used by Celery tasks."""

from __future__ import annotations

import shutil
from time import perf_counter
from uuid import uuid4

import requests
from django.conf import settings
from django.core.cache import cache
from django.db import connection

from apps.payments.providers.registry import registry
from core.services.api_health_service import APIHealthService


class ServerHealthService:
    """Health checks for server-level dependencies."""

    def check_all(self) -> list[dict]:
        return [
            self._check_database(),
            self._check_cache(),
            self._check_disk(),
        ]

    def _check_database(self) -> dict:
        started = perf_counter()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()

            latency_ms = self._elapsed_ms(started)
            return {
                "component": "database",
                "status": "healthy" if latency_ms < 800 else "warning",
                "response_time_ms": latency_ms,
                "message": "Database connectivity OK",
                "metadata": {"latency_ms": latency_ms},
            }
        except Exception as exc:
            return {
                "component": "database",
                "status": "down",
                "response_time_ms": self._elapsed_ms(started),
                "message": f"Database check failed: {exc}",
                "metadata": {"error_type": type(exc).__name__},
            }

    def _check_cache(self) -> dict:
        started = perf_counter()
        cache_key = f"health:cache:{uuid4().hex}"
        try:
            cache.set(cache_key, "ok", timeout=15)
            read_value = cache.get(cache_key)
            latency_ms = self._elapsed_ms(started)

            status = "healthy"
            message = "Cache read/write OK"
            if read_value != "ok":
                status = "degraded"
                message = "Cache write/read mismatch"

            return {
                "component": "cache",
                "status": status,
                "response_time_ms": latency_ms,
                "message": message,
                "metadata": {"latency_ms": latency_ms},
            }
        except Exception as exc:
            return {
                "component": "cache",
                "status": "down",
                "response_time_ms": self._elapsed_ms(started),
                "message": f"Cache check failed: {exc}",
                "metadata": {"error_type": type(exc).__name__},
            }
        finally:
            try:
                cache.delete(cache_key)
            except Exception:
                pass

    def _check_disk(self) -> dict:
        started = perf_counter()
        try:
            total, used, free = shutil.disk_usage(settings.BASE_DIR)
            used_pct = round((used / total) * 100, 2) if total else 0.0
            latency_ms = self._elapsed_ms(started)

            if used_pct >= 95:
                status = "down"
                message = f"Disk critical: {used_pct}% used"
            elif used_pct >= 85:
                status = "degraded"
                message = f"Disk high usage: {used_pct}% used"
            elif used_pct >= 75:
                status = "warning"
                message = f"Disk elevated usage: {used_pct}% used"
            else:
                status = "healthy"
                message = f"Disk usage healthy: {used_pct}% used"

            return {
                "component": "disk",
                "status": status,
                "response_time_ms": latency_ms,
                "message": message,
                "metadata": {
                    "total_bytes": total,
                    "used_bytes": used,
                    "free_bytes": free,
                    "used_percent": used_pct,
                },
            }
        except Exception as exc:
            return {
                "component": "disk",
                "status": "down",
                "response_time_ms": self._elapsed_ms(started),
                "message": f"Disk check failed: {exc}",
                "metadata": {"error_type": type(exc).__name__},
            }

    @staticmethod
    def _elapsed_ms(started: float) -> int:
        return int((perf_counter() - started) * 1000)


class APIHealthMonitorService:
    """Health checks for internal API endpoints."""

    def check_all(self) -> list[dict]:
        base_url = getattr(settings, "HEALTH_API_BASE_URL", "").strip() or "http://127.0.0.1:8000/api"
        timeout_seconds = float(getattr(settings, "HEALTH_API_TIMEOUT_SECONDS", 3.0))
        endpoints = tuple(getattr(settings, "HEALTH_API_ENDPOINTS", APIHealthService.DEFAULT_ENDPOINTS))

        checker = APIHealthService(
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            endpoints=endpoints,
        )
        raw_results = checker.check_all()

        normalized = []
        for item in raw_results:
            endpoint = item.get("endpoint") or "unknown"
            normalized.append(
                {
                    "component": f"endpoint:{endpoint}",
                    "status": item.get("health", "down"),
                    "response_time_ms": int(item.get("latency_ms") or 0),
                    "message": item.get("error") or f"HTTP {item.get('status_code')}",
                    "metadata": {
                        "url": item.get("url"),
                        "endpoint": endpoint,
                        "status_code": item.get("status_code"),
                    },
                }
            )
        return normalized


class PaymentHealthService:
    """Health checks for payment providers."""

    def check_all(self) -> list[dict]:
        checks: list[dict] = []
        providers = registry.all()
        if not providers:
            return [
                {
                    "component": "payment_registry",
                    "status": "down",
                    "response_time_ms": 0,
                    "message": "No payment providers registered",
                    "metadata": {},
                }
            ]

        for provider in providers:
            checks.append(self._check_provider(provider))
        return checks

    def _check_provider(self, provider) -> dict:
        provider_name = getattr(provider, "name", provider.__class__.__name__)
        probe_url = getattr(provider, "base_url", None)
        started = perf_counter()

        if not probe_url:
            return {
                "component": f"payment:{provider_name}",
                "status": "healthy",
                "response_time_ms": 0,
                "message": "Provider loaded successfully",
                "metadata": {"provider": provider_name, "probe": "load_only"},
            }

        try:
            response = requests.get(probe_url, timeout=5)
            latency_ms = int((perf_counter() - started) * 1000)

            if response.status_code >= 500:
                status = "down"
                message = f"Provider endpoint unhealthy ({response.status_code})"
            elif response.status_code >= 400:
                status = "warning"
                message = f"Provider reachable but returned {response.status_code}"
            elif latency_ms > 3000:
                status = "degraded"
                message = f"Provider slow response ({latency_ms}ms)"
            else:
                status = "healthy"
                message = "Provider reachable"

            return {
                "component": f"payment:{provider_name}",
                "status": status,
                "response_time_ms": latency_ms,
                "message": message,
                "metadata": {
                    "provider": provider_name,
                    "probe_url": probe_url,
                    "status_code": response.status_code,
                },
            }
        except requests.RequestException as exc:
            return {
                "component": f"payment:{provider_name}",
                "status": "down",
                "response_time_ms": int((perf_counter() - started) * 1000),
                "message": f"Provider probe failed: {exc}",
                "metadata": {"provider": provider_name, "probe_url": probe_url},
            }
