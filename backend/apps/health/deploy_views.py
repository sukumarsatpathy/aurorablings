from __future__ import annotations

from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from core.response import success_response

from .services import PaymentHealthService, ServerHealthService

# Health endpoints must never be throttled.
#
# DEFAULT_THROTTLE_CLASSES (settings.base) applies AnonRateThrottle to every
# view that does not opt out. AnonRateThrottle reads and writes the cache on
# every request, and the cache is Redis. So when Redis went down, the throttle
# raised *before the view ran* and /health/server returned 500 -- the health
# endpoint failed for the one reason it most needed to be able to report.
#
# The consequences cascaded. docker-compose.prod.yml's healthcheck is
# `curl -fL http://localhost:8000/health/server`, and -f treats 500 as failure,
# so the backend was marked unhealthy and restarted. entrypoint.sh then re-ran
# migrate and collectstatic --clear on every one of those restarts, with a 90s
# start_period. A brief cache blip therefore became a ~90 second hard outage,
# repeating for as long as Redis stayed unhappy.
#
# The check functions in services.py are already exception-safe: a dead cache
# yields {"status": "down"} inside a 200 response. That is the correct
# behaviour -- "cache down, app up" is real, reportable information, and
# restarting the app container does not fix Redis. With throttling off this
# path, the endpoint can finally say so.
#
# Monitoring should alert on the `status` field in the body, not on HTTP status.
THROTTLE_EXEMPT: list = []


class _UnthrottledHealthView(APIView):
    """Base for deploy/monitoring health endpoints. See THROTTLE_EXEMPT above."""

    permission_classes = [AllowAny]
    throttle_classes = THROTTLE_EXEMPT


def _status_priority(value: str) -> int:
    order = {
        "healthy": 0,
        "warning": 1,
        "degraded": 2,
        "down": 3,
    }
    return order.get((value or "").lower(), 3)


def _aggregate_status(checks: list[dict]) -> str:
    if not checks:
        return "down"
    return sorted((str(item.get("status") or "down") for item in checks), key=_status_priority, reverse=True)[0]


class PublicServerHealthView(_UnthrottledHealthView):

    def get(self, request):
        checks = ServerHealthService().check_all()
        return success_response(
            data={
                "status": _aggregate_status(checks),
                "checks": checks,
            },
            message="Server health check completed.",
        )


class PublicDBHealthView(_UnthrottledHealthView):

    def get(self, request):
        result = ServerHealthService()._check_database()
        return success_response(
            data={
                "status": result.get("status", "down"),
                "check": result,
            },
            message="Database health check completed.",
        )


class PublicCacheHealthView(_UnthrottledHealthView):

    def get(self, request):
        result = ServerHealthService()._check_cache()
        return success_response(
            data={
                "status": result.get("status", "down"),
                "check": result,
            },
            message="Cache health check completed.",
        )


class PublicPaymentHealthView(_UnthrottledHealthView):

    def get(self, request):
        checks = PaymentHealthService().check_all()
        return success_response(
            data={
                "status": _aggregate_status(checks),
                "checks": checks,
            },
            message="Payment health check completed.",
        )
