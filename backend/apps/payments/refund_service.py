from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import uuid4

from django.db import transaction

from core.exceptions import ValidationError
from core.logging import get_logger

from apps.orders.models import PaymentStatus
from apps.orders.services import mark_partially_refunded, mark_refunded
from apps.payments.models import (
    PaymentTransaction,
    Refund,
    RefundSource,
    RefundStatus,
    TransactionStatus,
)
from apps.payments.providers.registry import registry
from apps.payments.selectors import get_successful_transaction

logger = get_logger(__name__)


def _normalize_amount(value: Decimal | int | float | str) -> Decimal:
    amount = Decimal(str(value or '0')).quantize(Decimal('0.01'))
    if amount <= 0:
        raise ValidationError('Refund amount must be greater than zero.')
    return amount


def _next_refund_id() -> str:
    return f"RFND-{uuid4().hex[:12].upper()}"


def _clean(value: Any) -> str:
    return str(value or "").strip()


@transaction.atomic
def create_refund(
    *,
    order,
    payment: PaymentTransaction,
    amount: Decimal,
    source: str = RefundSource.MANUAL,
    reason: str = '',
    metadata: dict[str, Any] | None = None,
    changed_by=None,
) -> Refund:
    """
    Create a manual/auto refund request and persist a Refund row.

    For MANUAL source this calls provider API first, then applies status.
    For AUTO source this stores an initiated row only; webhook apply_refund handles final state.
    """
    if payment.order_id != order.id:
        raise ValidationError('Payment transaction does not belong to the order.')

    # Re-fetch with row lock to prevent concurrent refund race conditions
    payment = PaymentTransaction.objects.select_for_update().get(pk=payment.pk)

    if payment.status not in {
        TransactionStatus.SUCCESS,
        TransactionStatus.PARTIALLY_REFUNDED,
        TransactionStatus.REFUNDED,
    }:
        raise ValidationError('Refund can be initiated only for successful/partially refunded payments.')

    refund_amount = _normalize_amount(amount)
    outstanding = (payment.total_amount - payment.refunded_amount).quantize(Decimal('0.01'))
    if refund_amount > outstanding:
        raise ValidationError(
            'Refund amount exceeds refundable balance.',
            extra={
                'requested': str(refund_amount),
                'available': str(outstanding),
            },
        )

    refund = Refund.objects.create(
        order=order,
        payment=payment,
        refund_id=_next_refund_id(),
        amount=refund_amount,
        status=RefundStatus.INITIATED,
        source=source,
        metadata={
            **(metadata or {}),
            'reason': reason,
        },
    )

    logger.info(
        'refund_created',
        refund_id=refund.refund_id,
        order_id=str(order.id),
        payment_id=str(payment.id),
        amount=str(refund_amount),
        source=source,
    )

    if source == RefundSource.MANUAL:
        provider = registry.get(payment.provider)
        result = provider.refund(
            provider_ref=payment.provider_ref,
            amount=refund_amount,
            reason=reason,
        )

        if result.success:
            return apply_refund(
                payment=payment,
                refund_amount=refund_amount,
                refund_id=refund.refund_id,
                cf_refund_id=result.refund_ref,
                status=RefundStatus.SUCCESS,
                source=source,
                metadata={
                    **(metadata or {}),
                    'provider_response': result.raw_response,
                },
                changed_by=changed_by,
            )

        refund.status = RefundStatus.FAILED
        refund.cf_refund_id = result.refund_ref or ''
        refund.metadata = {
            **refund.metadata,
            'provider_error': result.error or 'Refund API failed',
            'provider_response': result.raw_response,
        }
        refund.save(update_fields=['status', 'cf_refund_id', 'metadata', 'updated_at'])
        logger.warning(
            'refund_manual_failed',
            refund_id=refund.refund_id,
            order_id=str(order.id),
            payment_id=str(payment.id),
            error=result.error,
        )

    return refund


@transaction.atomic
def apply_refund(
    *,
    payment: PaymentTransaction,
    refund_amount: Decimal,
    refund_id: str,
    cf_refund_id: str = '',
    status: str = RefundStatus.SUCCESS,
    source: str = RefundSource.AUTO,
    metadata: dict[str, Any] | None = None,
    changed_by=None,
) -> Refund:
    """
    Apply a refund outcome idempotently and update payment/order aggregate state.
    """
    amount_value = _normalize_amount(refund_amount)

    # Re-fetch with row lock to prevent concurrent refund race conditions
    payment = PaymentTransaction.objects.select_for_update().get(pk=payment.pk)

    refund, created = Refund.objects.get_or_create(
        refund_id=refund_id,
        defaults={
            'order': payment.order,
            'payment': payment,
            'amount': amount_value,
            'source': source,
            'status': RefundStatus.INITIATED,
            'cf_refund_id': cf_refund_id or '',
            'metadata': metadata or {},
        },
    )

    if not created:
        # Idempotent re-delivery: already applied successfully.
        if refund.status == RefundStatus.SUCCESS and status == RefundStatus.SUCCESS:
            return refund
        if refund.payment_id is None:
            refund.payment = payment

    refund.amount = amount_value
    refund.source = source
    refund.cf_refund_id = cf_refund_id or refund.cf_refund_id
    if metadata:
        refund.metadata = {**(refund.metadata or {}), **metadata}

    normalized_status = str(status or '').lower()
    if normalized_status in {RefundStatus.FAILED, RefundStatus.CANCELLED}:
        refund.status = normalized_status
        refund.save(update_fields=['payment', 'amount', 'source', 'cf_refund_id', 'metadata', 'status', 'updated_at'])
        return refund

    if normalized_status not in {RefundStatus.SUCCESS, RefundStatus.INITIATED}:
        refund.status = RefundStatus.FAILED
        refund.metadata = {**(refund.metadata or {}), 'error': f'Unsupported refund status: {normalized_status}'}
        refund.save(update_fields=['payment', 'amount', 'source', 'cf_refund_id', 'metadata', 'status', 'updated_at'])
        return refund

    # Pending/initiation events should be stored but not financially applied.
    if normalized_status == RefundStatus.INITIATED:
        refund.status = RefundStatus.INITIATED
        refund.save(update_fields=['payment', 'amount', 'source', 'cf_refund_id', 'metadata', 'status', 'updated_at'])
        return refund

    outstanding = (payment.total_amount - payment.refunded_amount).quantize(Decimal('0.01'))
    if amount_value > outstanding:
        raise ValidationError(
            'Refund amount exceeds outstanding refundable amount.',
            extra={'requested': str(amount_value), 'available': str(outstanding)},
        )

    payment.refunded_amount = (payment.refunded_amount + amount_value).quantize(Decimal('0.01'))
    if payment.refunded_amount >= payment.total_amount:
        payment.status = TransactionStatus.REFUNDED
        payment.refunded_amount = payment.total_amount
        payment.order.payment_status = PaymentStatus.REFUNDED
        payment.order.save(update_fields=['payment_status', 'updated_at'])
        mark_refunded(order=payment.order, reason='Refund synchronized.', changed_by=changed_by)
    else:
        payment.status = TransactionStatus.PARTIALLY_REFUNDED
        payment.order.payment_status = PaymentStatus.PARTIALLY_REFUNDED
        payment.order.save(update_fields=['payment_status', 'updated_at'])
        mark_partially_refunded(order=payment.order, reason='Partial refund synchronized.', changed_by=changed_by)

    payment.save(update_fields=['refunded_amount', 'status', 'updated_at'])

    refund.status = RefundStatus.SUCCESS
    refund.save(update_fields=['payment', 'amount', 'source', 'cf_refund_id', 'metadata', 'status', 'updated_at'])

    logger.info(
        'refund_applied',
        refund_id=refund.refund_id,
        cf_refund_id=refund.cf_refund_id,
        payment_id=str(payment.id),
        order_id=str(payment.order_id),
        refund_amount=str(amount_value),
        refunded_total=str(payment.refunded_amount),
        payment_status=payment.status,
        order_status=payment.order.status,
    )
    return refund


@transaction.atomic
def handle_refund_webhook(*, refund_data: dict[str, Any], provider_name: str = "cashfree") -> Refund | None:
    """
    Parse and apply Cashfree refund webhook idempotently.
    """
    order_id = _clean(refund_data.get("order_id") or refund_data.get("orderId"))
    cf_payment_id = _clean(
        refund_data.get("cf_payment_id")
        or refund_data.get("payment_id")
        or refund_data.get("paymentId")
    )
    refund_id = _clean(
        refund_data.get("refund_id")
        or refund_data.get("merchant_refund_id")
        or refund_data.get("refundId")
    )
    cf_refund_id = _clean(
        refund_data.get("cf_refund_id")
        or refund_data.get("cashfree_refund_id")
        or refund_data.get("cfRefundId")
    )
    refund_amount = _normalize_amount(
        refund_data.get("refund_amount")
        or refund_data.get("amount")
        or refund_data.get("refundAmount")
    )
    refund_status = _clean(refund_data.get("refund_status") or refund_data.get("status")).upper()

    if not refund_id:
        refund_id = f"CF-{cf_refund_id or cf_payment_id or order_id or 'UNKNOWN'}"

    txn = None
    if cf_payment_id:
        txn = (
            PaymentTransaction.objects
            .filter(provider=provider_name, provider_ref=cf_payment_id)
            .order_by("-created_at")
            .first()
        )
    if txn is None and order_id:
        txn = get_successful_transaction(order_id)

    if txn is None:
        logger.warning(
            "refund_webhook_transaction_not_found",
            provider=provider_name,
            order_id=order_id,
            cf_payment_id=cf_payment_id,
            refund_id=refund_id,
        )
        return None

    status_map = {
        "SUCCESS": RefundStatus.SUCCESS,
        "PROCESSED": RefundStatus.SUCCESS,
        "FAILED": RefundStatus.FAILED,
        "CANCELLED": RefundStatus.CANCELLED,
        "PENDING": RefundStatus.INITIATED,
    }
    normalized_status = status_map.get(refund_status, RefundStatus.FAILED)

    return apply_refund(
        payment=txn,
        refund_amount=refund_amount,
        refund_id=refund_id,
        cf_refund_id=cf_refund_id,
        status=normalized_status,
        source=RefundSource.AUTO,
        metadata={
            "provider": provider_name,
            "webhook_refund_status": refund_status,
            "raw_refund_data": refund_data,
        },
    )
