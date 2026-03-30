"""
orders.selectors
~~~~~~~~~~~~~~~~
Read-only queries for the orders system.
"""

from __future__ import annotations

from django.db.models import QuerySet, Prefetch
from .models import Order, OrderItem, OrderStatusHistory, OrderStatus


# ─────────────────────────────────────────────────────────────
#  Order retrieval
# ─────────────────────────────────────────────────────────────

def get_order_by_id(order_id, *, user=None) -> Order | None:
    """
    Return a fully prefetched order.
    If `user` is provided, scope to that user's orders.
    """
    try:
        qs = (
            Order.objects
            .select_related("user", "warehouse")
            .prefetch_related(
                Prefetch("items", queryset=OrderItem.objects.select_related("variant__product")),
                Prefetch("status_history", queryset=OrderStatusHistory.objects.order_by("created_at")),
                "shipment__events",
            )
        )
        if user and not (user.role in ("admin", "staff")):
            qs = qs.filter(user=user)
        return qs.get(id=order_id)
    except Order.DoesNotExist:
        return None


def get_order_by_number(order_number: str, *, user=None) -> Order | None:
    try:
        qs = Order.objects.select_related("user", "warehouse").prefetch_related("items", "status_history")
        if user and not (user.role in ("admin", "staff")):
            qs = qs.filter(user=user)
        return qs.get(order_number=order_number)
    except Order.DoesNotExist:
        return None


# ─────────────────────────────────────────────────────────────
#  Order lists
# ─────────────────────────────────────────────────────────────

def get_orders_for_user(user, *, status: str | None = None) -> QuerySet:
    qs = (
        Order.objects
        .filter(user=user)
        .select_related("warehouse")
        .prefetch_related("items", "shipment__events")
        .order_by("-created_at")
    )
    if status:
        qs = qs.filter(status=status)
    return qs


def get_all_orders(
    *,
    status: str | None = None,
    payment_status: str | None = None,
    user_id=None,
    search: str | None = None,
) -> QuerySet:
    """Admin-level order list with optional filters."""
    qs = (
        Order.objects
        .select_related("user", "warehouse")
        .prefetch_related("items", "shipment__events")
        .order_by("-created_at")
    )
    if status:
        qs = qs.filter(status=status)
    if payment_status:
        qs = qs.filter(payment_status=payment_status)
    if user_id:
        qs = qs.filter(user_id=user_id)
    if search:
        from django.db.models import Q
        qs = qs.filter(
            Q(order_number__icontains=search) |
            Q(user__email__icontains=search) |
            Q(guest_email__icontains=search) |
            Q(items__sku__icontains=search)
        ).distinct()
    return qs


# ─────────────────────────────────────────────────────────────
#  Status history
# ─────────────────────────────────────────────────────────────

def get_status_history(order: Order) -> QuerySet:
    return (
        OrderStatusHistory.objects
        .filter(order=order)
        .select_related("changed_by")
        .order_by("created_at")
    )
