from django.db.models import Avg, Count, F, OuterRef, Subquery
from django.utils.dateparse import parse_datetime
from django.utils.timezone import now
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdminUser
from core.pagination import StandardResultsPagination
from core.response import success_response

from .models import AlertSeverity, HealthAlert, HealthCheckResult, HealthSource, HealthStatus
from .serializers import HealthAlertSerializer, HealthCheckResultSerializer, HealthSummarySerializer


class AdminHealthBaseAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]
    pagination_class = StandardResultsPagination

    def _paginate(self, request, queryset, serializer_class, message="Data retrieved successfully.", aggregates=None):
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = serializer_class(page, many=True, context={"request": request})
        meta = paginator._build_meta()
        if aggregates:
            meta["aggregates"] = aggregates
        return success_response(data=serializer.data, meta=meta, message=message)


def _apply_check_filters(queryset, params):
    source = params.get("source")
    status = params.get("status")
    component = params.get("component")
    checked_after = parse_datetime(params.get("checked_after", "")) if params.get("checked_after") else None
    checked_before = parse_datetime(params.get("checked_before", "")) if params.get("checked_before") else None

    if source in HealthSource.values:
        queryset = queryset.filter(source=source)
    if status in HealthStatus.values:
        queryset = queryset.filter(status=status)
    if component:
        queryset = queryset.filter(component__icontains=component.strip())
    if checked_after:
        queryset = queryset.filter(checked_at__gte=checked_after)
    if checked_before:
        queryset = queryset.filter(checked_at__lte=checked_before)
    return queryset


def _apply_alert_filters(queryset, params):
    severity = params.get("severity")
    component = params.get("component")
    is_resolved = params.get("is_resolved")
    created_after = parse_datetime(params.get("created_after", "")) if params.get("created_after") else None
    created_before = parse_datetime(params.get("created_before", "")) if params.get("created_before") else None

    if severity in AlertSeverity.values:
        queryset = queryset.filter(severity=severity)
    if component:
        queryset = queryset.filter(component__icontains=component.strip())
    if is_resolved in {"true", "false"}:
        queryset = queryset.filter(is_resolved=(is_resolved == "true"))
    if created_after:
        queryset = queryset.filter(created_at__gte=created_after)
    if created_before:
        queryset = queryset.filter(created_at__lte=created_before)
    return queryset


def _latest_checks_queryset():
    latest_result_id = (
        HealthCheckResult.objects.filter(
            source=OuterRef("source"),
            component=OuterRef("component"),
        )
        .order_by("-checked_at", "-id")
        .values("id")[:1]
    )
    return (
        HealthCheckResult.objects.annotate(latest_id=Subquery(latest_result_id))
        .filter(id=F("latest_id"))
        .order_by("-checked_at")
    )


class HealthSummaryView(AdminHealthBaseAPIView):
    def get(self, request):
        latest_qs = _apply_check_filters(_latest_checks_queryset(), request.query_params)
        alert_qs = _apply_alert_filters(HealthAlert.objects.all(), request.query_params)

        total_components = latest_qs.count()
        status_counts = {item["status"]: item["count"] for item in latest_qs.values("status").annotate(count=Count("id"))}
        source_counts = {item["source"]: item["count"] for item in latest_qs.values("source").annotate(count=Count("id"))}
        response_time_agg = latest_qs.exclude(response_time_ms__isnull=True).aggregate(avg=Avg("response_time_ms"))
        latest_check = latest_qs.first()

        overall_status = HealthStatus.HEALTHY
        if status_counts.get(HealthStatus.DOWN):
            overall_status = HealthStatus.DOWN
        elif status_counts.get(HealthStatus.DEGRADED):
            overall_status = HealthStatus.DEGRADED
        elif status_counts.get(HealthStatus.WARNING):
            overall_status = HealthStatus.WARNING

        payload = {
            "generated_at": now(),
            "overall_status": overall_status,
            "total_components": total_components,
            "status_distribution": status_counts,
            "source_distribution": source_counts,
            "open_alerts": alert_qs.filter(is_resolved=False).count(),
            "resolved_alerts": alert_qs.filter(is_resolved=True).count(),
            "latest_check_at": latest_check.checked_at if latest_check else None,
            "avg_response_time_ms": response_time_agg["avg"],
        }
        serializer = HealthSummarySerializer(payload)
        return success_response(data=serializer.data, message="Health summary retrieved successfully.")


class HealthDetailedView(AdminHealthBaseAPIView):
    def get(self, request):
        queryset = _apply_check_filters(_latest_checks_queryset(), request.query_params)
        aggregates = {
            "status_distribution": {
                item["status"]: item["count"]
                for item in queryset.values("status").annotate(count=Count("id"))
            },
            "source_distribution": {
                item["source"]: item["count"]
                for item in queryset.values("source").annotate(count=Count("id"))
            },
        }
        return self._paginate(
            request=request,
            queryset=queryset,
            serializer_class=HealthCheckResultSerializer,
            message="Detailed health results retrieved successfully.",
            aggregates=aggregates,
        )


class HealthHistoryView(AdminHealthBaseAPIView):
    def get(self, request):
        queryset = _apply_check_filters(HealthCheckResult.objects.all().order_by("-checked_at"), request.query_params)
        aggregates = {
            "latest_check_at": queryset.first().checked_at if queryset.exists() else None,
            "status_distribution": {
                item["status"]: item["count"]
                for item in queryset.values("status").annotate(count=Count("id"))
            },
        }
        return self._paginate(
            request=request,
            queryset=queryset,
            serializer_class=HealthCheckResultSerializer,
            message="Health history retrieved successfully.",
            aggregates=aggregates,
        )


class HealthAlertsView(AdminHealthBaseAPIView):
    def get(self, request):
        queryset = _apply_alert_filters(HealthAlert.objects.all().order_by("-created_at"), request.query_params)
        aggregates = {
            "open_alerts": queryset.filter(is_resolved=False).count(),
            "resolved_alerts": queryset.filter(is_resolved=True).count(),
            "severity_distribution": {
                item["severity"]: item["count"]
                for item in queryset.values("severity").annotate(count=Count("id"))
            },
        }
        return self._paginate(
            request=request,
            queryset=queryset,
            serializer_class=HealthAlertSerializer,
            message="Health alerts retrieved successfully.",
            aggregates=aggregates,
        )
