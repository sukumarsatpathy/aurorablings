"""
payments.tasks
~~~~~~~~~~~~~~
Celery tasks for async payment operations.

Retry strategy (exponential backoff):
  Attempt 1 → immediate
  Attempt 2 → 60s delay
  Attempt 3 → 300s delay (5 min)
  max_retries = 3 (configurable per transaction)
"""
from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,       # base delay seconds
    autoretry_for=(Exception,),
    retry_backoff=True,           # exponential: 60, 120, 240
    retry_backoff_max=600,        # cap at 10 minutes
)
def retry_failed_payment_task(self, transaction_id: str, return_url: str = ""):
    """
    Called automatically when a payment fails.
    Retries up to max_retries times with exponential backoff.
    """
    from .models import PaymentTransaction
    from .services import retry_payment
    from core.exceptions import ValidationError

    try:
        txn = PaymentTransaction.objects.select_related("order").get(id=transaction_id)
    except PaymentTransaction.DoesNotExist:
        logger.error(f"Transaction {transaction_id} not found.")
        return

    if not txn.can_retry:
        logger.info(f"Transaction {transaction_id} retry limit reached — aborting.")
        return

    try:
        new_txn = retry_payment(transaction=txn, return_url=return_url)
        logger.info(
            f"Retry succeeded for transaction {transaction_id}. "
            f"New transaction: {new_txn.id}"
        )
    except ValidationError as exc:
        logger.warning(f"Retry validation error: {exc}")
    except Exception as exc:
        logger.error(f"Retry failed for {transaction_id}: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True)
def process_webhook_task(self, provider_name: str, payload_str: str, headers: dict):
    """
    Process a webhook asynchronously.
    The view immediately logs the raw payload and enqueues this task.
    """
    from .services import handle_webhook

    try:
        handle_webhook(
            provider_name=provider_name,
            payload=payload_str.encode("utf-8"),
            headers=headers,
        )
    except Exception as exc:
        logger.exception(f"Webhook processing failed for {provider_name}: {exc}")
        raise self.retry(exc=exc, countdown=30, max_retries=5)


@shared_task(name="payments.expire_stale_razorpay_orders")
def expire_stale_razorpay_orders_task():
    """
    Safety net for abandoned Razorpay checkout flows.

    Reconciles stale unpaid Razorpay transactions and cancels orders that remain
    unpaid beyond the configured timeout, releasing reserved stock.
    """
    from datetime import timedelta

    from django.conf import settings
    from django.utils import timezone

    from apps.orders.models import PaymentStatus
    from apps.orders.services import cancel_order
    from apps.payments.models import PaymentTransaction, TransactionStatus
    from apps.payments.services import reconcile_transaction_status
    from core.exceptions import ConflictError

    stale_after_minutes = max(
        1,
        int(getattr(settings, "RAZORPAY_STALE_ORDER_TIMEOUT_MINUTES", 20) or 20),
    )
    cutoff = timezone.now() - timedelta(minutes=stale_after_minutes)
    stale_statuses = [
        TransactionStatus.CREATED,
        TransactionStatus.PENDING,
        TransactionStatus.RETRY,
    ]

    stale_candidates = (
        PaymentTransaction.objects
        .select_related("order")
        .filter(
            provider="razorpay",
            status__in=stale_statuses,
            created_at__lte=cutoff,
        )
        .order_by("created_at")
    )

    scanned = 0
    cancelled = 0
    skipped = 0

    for txn in stale_candidates:
        scanned += 1

        latest_for_order = (
            PaymentTransaction.objects
            .filter(order_id=txn.order_id)
            .order_by("-created_at")
            .first()
        )
        if not latest_for_order or latest_for_order.id != txn.id:
            skipped += 1
            continue

        if PaymentTransaction.objects.filter(
            order_id=txn.order_id,
            status=TransactionStatus.SUCCESS,
        ).exists():
            skipped += 1
            continue

        try:
            txn = reconcile_transaction_status(transaction=txn)
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "razorpay_stale_reconcile_failed",
                transaction_id=str(txn.id),
                order_id=str(txn.order_id),
                error=str(exc),
            )
            skipped += 1
            continue

        if txn.status == TransactionStatus.SUCCESS:
            skipped += 1
            continue

        reason = (
            f"Auto-cancelled: unpaid Razorpay checkout expired after {stale_after_minutes} minutes."
        )
        if txn.status not in {TransactionStatus.FAILED, TransactionStatus.CANCELLED}:
            txn.status = TransactionStatus.FAILED
            txn.last_error = reason
            txn.save(update_fields=["status", "last_error", "updated_at"])

        order = txn.order
        if order.payment_status != PaymentStatus.FAILED:
            order.payment_status = PaymentStatus.FAILED
            order.save(update_fields=["payment_status", "updated_at"])

        try:
            cancel_order(order=order, changed_by=None, reason=reason)
            cancelled += 1
            logger.info(
                "razorpay_stale_order_cancelled",
                order_id=str(order.id),
                transaction_id=str(txn.id),
            )
        except ConflictError:
            skipped += 1
            logger.info(
                "razorpay_stale_order_not_cancellable",
                order_id=str(order.id),
                order_status=order.status,
                transaction_id=str(txn.id),
            )
        except Exception as exc:  # noqa: BLE001
            skipped += 1
            logger.exception(
                "razorpay_stale_order_cancel_failed",
                order_id=str(order.id),
                transaction_id=str(txn.id),
                error=str(exc),
            )

    logger.info(
        "razorpay_stale_cleanup_completed",
        scanned=scanned,
        cancelled=cancelled,
        skipped=skipped,
        stale_after_minutes=stale_after_minutes,
    )
    return {
        "scanned": scanned,
        "cancelled": cancelled,
        "skipped": skipped,
        "stale_after_minutes": stale_after_minutes,
    }
