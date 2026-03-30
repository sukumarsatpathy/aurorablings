"""
payments.selectors
~~~~~~~~~~~~~~~~~~
"""
from __future__ import annotations
from django.db.models import QuerySet
from .models import PaymentTransaction, WebhookLog, Refund, TransactionStatus


def get_transaction_by_id(txn_id) -> PaymentTransaction | None:
    try:
        return PaymentTransaction.objects.select_related("order", "initiated_by").get(id=txn_id)
    except PaymentTransaction.DoesNotExist:
        return None


def get_transactions_for_order(order_id) -> QuerySet:
    return (
        PaymentTransaction.objects
        .filter(order_id=order_id)
        .select_related("initiated_by")
        .order_by("-created_at")
    )


def get_successful_transaction(order_id) -> PaymentTransaction | None:
    return (
        PaymentTransaction.objects
        .filter(
            order_id=order_id,
            status__in=(
                TransactionStatus.SUCCESS,
                TransactionStatus.PARTIALLY_REFUNDED,
            ),
        )
        .order_by("-created_at")
        .first()
    )


def get_webhook_logs(
    *,
    provider: str | None = None,
    is_processed: bool | None = None,
    limit: int = 100,
) -> QuerySet:
    qs = WebhookLog.objects.all()
    if provider:
        qs = qs.filter(provider=provider)
    if is_processed is not None:
        qs = qs.filter(is_processed=is_processed)
    return qs.order_by("-created_at")[:limit]


def get_refund_by_refund_id(refund_id: str) -> Refund | None:
    try:
        return Refund.objects.select_related("order", "payment").get(refund_id=refund_id)
    except Refund.DoesNotExist:
        return None


def get_refunds_for_order(order_id) -> QuerySet:
    return (
        Refund.objects
        .filter(order_id=order_id)
        .select_related("payment")
        .order_by("-created_at")
    )
