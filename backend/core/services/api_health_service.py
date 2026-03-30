"""core.services.api_health_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Service for checking health of critical Aurora Blings APIs.
"""

from __future__ import annotations

from time import perf_counter
from typing import Any

import requests


class APIHealthService:
    """Checks configured endpoints and returns structured health results."""

    DEFAULT_ENDPOINTS = (
        "/v1/catalog/health/",
        "/v1/cart/health/",
        "/v1/checkout/health/",
        "/v1/system/ping/",
    )

    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float = 3.0,
        endpoints: tuple[str, ...] | list[str] | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.endpoints = tuple(endpoints or self.DEFAULT_ENDPOINTS)
        self.session = session or requests.Session()

    def check_all(self) -> list[dict[str, Any]]:
        """Run health checks for all configured endpoints."""
        return [self._check_endpoint(endpoint) for endpoint in self.endpoints]

    def _check_endpoint(self, endpoint: str) -> dict[str, Any]:
        url = self._build_url(endpoint)
        started = perf_counter()

        try:
            response = self.session.get(url, timeout=self.timeout_seconds)
            latency_ms = self._elapsed_ms(started)

            return {
                "endpoint": endpoint,
                "url": url,
                "status_code": response.status_code,
                "latency_ms": latency_ms,
                "health": self._evaluate_health(response.status_code, latency_ms),
                "error": None,
            }

        except requests.Timeout:
            latency_ms = self._elapsed_ms(started)
            return {
                "endpoint": endpoint,
                "url": url,
                "status_code": None,
                "latency_ms": latency_ms,
                "health": "down",
                "error": f"Request timed out after {self.timeout_seconds} seconds",
            }

        except requests.RequestException as exc:
            latency_ms = self._elapsed_ms(started)
            return {
                "endpoint": endpoint,
                "url": url,
                "status_code": None,
                "latency_ms": latency_ms,
                "health": "down",
                "error": str(exc),
            }

    def _evaluate_health(self, status_code: int | None, latency_ms: float) -> str:
        if status_code is None or status_code >= 500:
            return "down"
        if latency_ms > 2500:
            return "degraded"
        if latency_ms > 1200:
            return "warning"
        return "healthy"

    def _build_url(self, endpoint: str) -> str:
        normalized_endpoint = endpoint if endpoint.startswith("/") else f"/{endpoint}"
        return f"{self.base_url}{normalized_endpoint}"

    @staticmethod
    def _elapsed_ms(started: float) -> float:
        return round((perf_counter() - started) * 1000, 2)
