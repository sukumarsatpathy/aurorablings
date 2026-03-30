from __future__ import annotations

from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from core.response import success_response

from .services import PaymentHealthService, ServerHealthService


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


class PublicServerHealthView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        checks = ServerHealthService().check_all()
        return success_response(
            data={
                "status": _aggregate_status(checks),
                "checks": checks,
            },
            message="Server health check completed.",
        )


class PublicDBHealthView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        result = ServerHealthService()._check_database()
        return success_response(
            data={
                "status": result.get("status", "down"),
                "check": result,
            },
            message="Database health check completed.",
        )


class PublicCacheHealthView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        result = ServerHealthService()._check_cache()
        return success_response(
            data={
                "status": result.get("status", "down"),
                "check": result,
            },
            message="Cache health check completed.",
        )


class PublicPaymentHealthView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        checks = PaymentHealthService().check_all()
        return success_response(
            data={
                "status": _aggregate_status(checks),
                "checks": checks,
            },
            message="Payment health check completed.",
        )
