"""returns.selectors — read-only queries."""
from __future__ import annotations
from django.db.models import QuerySet, Prefetch
from .models import ReturnRequest, ReturnItem, ExchangeRequest, ExchangeItem, ReturnStatusHistory


# ── Return Requests ───────────────────────────────────────────

def get_return_by_id(rr_id, *, user=None) -> ReturnRequest | None:
    try:
        qs = (
            ReturnRequest.objects
            .select_related("order", "user")
            .prefetch_related(
                Prefetch("items", queryset=ReturnItem.objects.select_related("variant", "order_item", "warehouse")),
                Prefetch("status_history", queryset=ReturnStatusHistory.objects.order_by("created_at")),
            )
        )
        if user and user.role not in ("admin", "staff"):
            qs = qs.filter(user=user)
        return qs.get(id=rr_id)
    except ReturnRequest.DoesNotExist:
        return None


def get_returns_for_user(user) -> QuerySet:
    return (
        ReturnRequest.objects
        .filter(user=user)
        .select_related("order")
        .prefetch_related("items")
        .order_by("-created_at")
    )


def get_all_returns(
    *,
    status: str | None = None,
    is_refund_ready: bool | None = None,
    order_id=None,
) -> QuerySet:
    qs = ReturnRequest.objects.select_related("order", "user").prefetch_related("items")
    if status:
        qs = qs.filter(status=status)
    if is_refund_ready is not None:
        qs = qs.filter(is_refund_ready=is_refund_ready)
    if order_id:
        qs = qs.filter(order_id=order_id)
    return qs.order_by("-created_at")


# ── Exchange Requests ─────────────────────────────────────────

def get_exchange_by_id(exc_id, *, user=None) -> ExchangeRequest | None:
    try:
        qs = (
            ExchangeRequest.objects
            .select_related("order", "user")
            .prefetch_related(
                Prefetch("items", queryset=ExchangeItem.objects.select_related(
                    "original_variant", "replacement_variant", "order_item"
                )),
                Prefetch("status_history", queryset=ReturnStatusHistory.objects.order_by("created_at")),
            )
        )
        if user and user.role not in ("admin", "staff"):
            qs = qs.filter(user=user)
        return qs.get(id=exc_id)
    except ExchangeRequest.DoesNotExist:
        return None


def get_exchanges_for_user(user) -> QuerySet:
    return (
        ExchangeRequest.objects
        .filter(user=user)
        .select_related("order")
        .prefetch_related("items")
        .order_by("-created_at")
    )


def get_all_exchanges(*, status: str | None = None, order_id=None) -> QuerySet:
    qs = ExchangeRequest.objects.select_related("order", "user").prefetch_related("items")
    if status:
        qs = qs.filter(status=status)
    if order_id:
        qs = qs.filter(order_id=order_id)
    return qs.order_by("-created_at")
