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
