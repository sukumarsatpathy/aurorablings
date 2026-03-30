from datetime import date, datetime, timedelta

from django.conf import settings
from django.db import models
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate, Coalesce
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated

from apps.accounts.permissions import IsStaffOrAdmin
from apps.inventory.models import WarehouseStock
from apps.notifications.models import ContactQuery
from apps.orders.models import Order, OrderStatus
from apps.pricing.coupons.models import CouponUsage

from core.response import success_response


@api_view(["GET"])
@permission_classes([AllowAny])
def api_root(request):
    """Welcome endpoint — lists key API entry points."""
    return success_response(
        data={
            "application": "Aurora Blings API",
            "version": "v1",
            "environment": "development" if settings.DEBUG else "production",
            "docs": request.build_absolute_uri("/api/docs/"),
            "health": request.build_absolute_uri("/health/"),
        },
        message="Welcome to Aurora Blings API.",
        request_id=getattr(request, "request_id", None),
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    """
    Lightweight liveness probe for container orchestration.
    Full health-check stack lives at /health/ (django-health-check).
    """
    return success_response(
        data={"status": "healthy"},
        message="Service is running.",
        request_id=getattr(request, "request_id", None),
    )


def _date_range_from_request(request) -> tuple[datetime, datetime, str, str, int | None]:
    tz_offset_raw = request.query_params.get("tz_offset")
    tz_offset = None
    if tz_offset_raw is not None:
        try:
            tz_offset = int(tz_offset_raw)
        except ValueError:
            tz_offset = None

    tz = timezone.get_fixed_timezone(tz_offset or 0)
    now = timezone.now().astimezone(tz)
    key = (request.query_params.get("range") or "today").lower()

    if key == "yesterday":
        day = now.date() - timedelta(days=1)
        start = datetime.combine(day, datetime.min.time())
        end = datetime.combine(day, datetime.max.time())
        label = "Yesterday"
    elif key in {"day_before_yesterday", "day-before-yesterday"}:
        day = now.date() - timedelta(days=2)
        start = datetime.combine(day, datetime.min.time())
        end = datetime.combine(day, datetime.max.time())
        label = "Day Before Yesterday"
    elif key == "last_month":
        first_of_this_month = date(year=now.year, month=now.month, day=1)
        last_month_end = first_of_this_month - timedelta(days=1)
        last_month_start = date(year=last_month_end.year, month=last_month_end.month, day=1)
        start = datetime.combine(last_month_start, datetime.min.time())
        end = datetime.combine(last_month_end, datetime.max.time())
        label = "Last Month"
    elif key == "custom":
        raw_from = request.query_params.get("date_from")
        raw_to = request.query_params.get("date_to")
        if raw_from:
            start_date = date.fromisoformat(raw_from)
        else:
            start_date = now.date()
        if raw_to:
            end_date = date.fromisoformat(raw_to)
        else:
            end_date = start_date
        start = datetime.combine(start_date, datetime.min.time())
        end = datetime.combine(end_date, datetime.max.time())
        label = "Custom Range"
    else:
        start = datetime.combine(now.date(), datetime.min.time())
        end = datetime.combine(now.date(), datetime.max.time())
        label = "Today"

    if timezone.is_naive(start):
        start = timezone.make_aware(start, tz)
    if timezone.is_naive(end):
        end = timezone.make_aware(end, tz)
    return start, end, label, key, tz_offset


def _build_series(start: datetime, end: datetime, by_date: dict[date, float | int]) -> list[dict]:
    series: list[dict] = []
    cursor = start.date()
    last = end.date()
    while cursor <= last:
        series.append({"date": cursor.isoformat(), "value": by_date.get(cursor, 0)})
        cursor = cursor + timedelta(days=1)
    return series


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsStaffOrAdmin])
def admin_dashboard(request):
    start, end, label, key, tz_offset = _date_range_from_request(request)

    effective_date_expr = Coalesce("placed_at", "created_at")

    orders_qs = (
        Order.objects.annotate(effective_date=effective_date_expr)
        .filter(effective_date__gte=start, effective_date__lte=end)
    )
    revenue_total = orders_qs.exclude(status=OrderStatus.CANCELLED).aggregate(total=Sum("grand_total"))["total"] or 0
    orders_total = orders_qs.count()
    shipping_orders_qs = orders_qs.filter(status__in=[OrderStatus.SHIPPED, OrderStatus.PROCESSING])

    orders_by_date = (
        orders_qs.annotate(day=TruncDate("effective_date"))
        .values("day")
        .annotate(count=Count("id"))
        .order_by("day")
    )
    revenue_by_date = (
        orders_qs.exclude(status=OrderStatus.CANCELLED)
        .annotate(day=TruncDate("effective_date"))
        .values("day")
        .annotate(total=Sum("grand_total"))
        .order_by("day")
    )

    order_series_map = {row["day"]: int(row["count"]) for row in orders_by_date}
    revenue_series_map = {row["day"]: float(row["total"] or 0) for row in revenue_by_date}

    coupon_usage_qs = CouponUsage.objects.filter(used_at__gte=start, used_at__lte=end)
    coupon_by_date = (
        coupon_usage_qs.annotate(day=TruncDate("used_at"))
        .values("day")
        .annotate(count=Count("id"))
        .order_by("day")
    )
    coupon_series_map = {row["day"]: int(row["count"]) for row in coupon_by_date}

    recent_orders = list(
        orders_qs.select_related("user")
        .order_by("-effective_date")[:6]
        .values(
            "id",
            "order_number",
            "status",
            "grand_total",
            "created_at",
            "user__email",
        )
    )

    recent_stock = list(
        WarehouseStock.objects.select_related("variant__product", "warehouse")
        .order_by("-updated_at")[:6]
        .values(
            "id",
            "variant__sku",
            "variant__product__name",
            "warehouse__code",
            "available",
            "updated_at",
        )
    )

    shipping_orders = list(
        shipping_orders_qs.select_related("user")
        .order_by("-updated_at")[:6]
        .values(
            "id",
            "order_number",
            "status",
            "tracking_number",
            "shipping_carrier",
            "updated_at",
            "user__email",
        )
    )

    coupon_usage = list(
        coupon_usage_qs.select_related("coupon", "user", "order")
        .order_by("-used_at")[:8]
        .values(
            "id",
            "coupon__code",
            "discount_amount",
            "used_at",
            "user__email",
            "order__order_number",
        )
    )

    low_stock_count = WarehouseStock.objects.filter(available__lte=models.F("low_stock_threshold")).count()
    contact_qs = ContactQuery.objects.filter(created_at__gte=start, created_at__lte=end)
    unread_contact_qs = ContactQuery.objects.filter(is_read=False)

    recent_contact_queries = list(
        contact_qs.order_by("-created_at")[:6].values(
            "id",
            "name",
            "email",
            "phone",
            "subject",
            "status",
            "is_read",
            "created_at",
        )
    )

    response = {
        "range": {
            "label": label,
            "date_from": start.date().isoformat(),
            "date_to": end.date().isoformat(),
        },
        "summary": {
            "total_revenue": str(revenue_total),
            "total_orders": orders_total,
            "shipping_orders": shipping_orders_qs.count(),
            "coupon_uses": coupon_usage_qs.count(),
            "low_stock_count": low_stock_count,
            "contact_queries": contact_qs.count(),
            "unread_contact_queries": unread_contact_qs.count(),
        },
        "charts": {
            "revenue": _build_series(start, end, revenue_series_map),
            "orders": _build_series(start, end, order_series_map),
            "coupons": _build_series(start, end, coupon_series_map),
        },
        "recent_orders": recent_orders,
        "recent_stock": recent_stock,
        "shipping_orders": shipping_orders,
        "coupon_usage": coupon_usage,
        "recent_contact_queries": recent_contact_queries,
        "referral": {
            "revenue": "0",
            "user_earning": "0",
            "referrer_earning": "0",
            "top_referrers": [],
        },
    }
    if settings.DEBUG:
        response["debug"] = {
            "range_key": key,
            "tz_offset": tz_offset,
            "start": start.isoformat(),
            "end": end.isoformat(),
        }
    return success_response(
        data=response,
        message="Dashboard metrics loaded.",
        request_id=getattr(request, "request_id", None),
    )
