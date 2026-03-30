from celery import shared_task
from celery.utils.log import get_task_logger
from django.conf import settings

logger = get_task_logger(__name__)


@shared_task(
    bind=True,
    name="notifications.send_notification",
    max_retries=5,
    default_retry_delay=60,
    retry_backoff=True,
    retry_backoff_max=1800,
    retry_jitter=True,
)
def send_notification_task(self, notification_id: str):
    from .services.notification_service import NotificationService
    from .models import NotificationStatus

    notification = NotificationService.send_notification(notification_id=notification_id)
    if not notification:
        return None

    if notification.status == NotificationStatus.FAILED and notification.can_retry:
        countdown = min(1800, 2 ** notification.retry_count)
        raise self.retry(countdown=countdown)

    return str(notification.id)


@shared_task(name="notifications.resend_failed_notification")
def resend_failed_notification_task(notification_id: str):
    from .services.notification_service import NotificationService

    result = NotificationService.resend_failed_notification(notification_id=notification_id)
    return str(result.id) if result else None


@shared_task(name="notifications.retry_pending")
def retry_pending_notifications_task():
    from .models import Notification, NotificationStatus

    failed = Notification.objects.filter(status=NotificationStatus.FAILED).order_by("-created_at")[:100]
    queued = 0
    for row in failed:
        if row.can_retry:
            send_notification_task.delay(str(row.id))
            queued += 1

    if queued:
        logger.info("retry_pending_notifications_queued", queued=queued)
    return queued


@shared_task(name="notifications.trigger_event_task")
def trigger_event_task(event: str, context: dict, user_id=None, recipient_email: str = "", recipient_phone: str = ""):
    from apps.accounts.models import User
    from .services.notification_service import trigger_event

    user = None
    if user_id:
        user = User.objects.filter(id=user_id).first()

    notifications = trigger_event(
        event=event,
        context=context,
        recipient_user=user,
        recipient_email=recipient_email,
        recipient_phone=recipient_phone,
    )
    return len(notifications)


@shared_task(name="notifications.notify_back_in_stock")
def notify_back_in_stock_task(product_id: str):
    from apps.notifications.events import NotificationEvent
    from apps.notifications.models import NotifySubscription
    from apps.catalog.models import ProductStockNotifyRequest
    from .services.notification_service import NotificationService

    subscriptions = (
        NotifySubscription.objects.select_related("product", "user")
        .filter(product_id=product_id, is_active=True, is_notified=False)
        .order_by("created_at")
    )

    sent = 0

    def _send_restock_email(*, recipient: str, user, customer_name: str, product_name: str, product_slug: str, product_image_url: str = ""):
        NotificationService.create_notification(
            event_type=NotificationEvent.PRODUCT_RESTOCKED,
            payload={
                "product_name": product_name,
                "product": {
                    "name": product_name,
                    "image_url": product_image_url,
                },
                "customer_name": customer_name,
                "user_name": customer_name,
                "product_id": str(product_id),
                "product_url": f"/products/{product_slug}/",
            },
            user=user,
            email=recipient,
            send_async=True,
        )

    for row in subscriptions:
        recipient = row.email or (row.user.email if row.user_id and row.user else "")
        if not recipient:
            continue

        media = row.product.media.filter(is_primary=True).first() or row.product.media.first()
        product_image_url = ""
        if media and getattr(media, "image", None):
            image_url = str(media.image.url or "")
            backend_url = str(getattr(settings, "BACKEND_URL", "") or "").rstrip("/")
            product_image_url = image_url if image_url.startswith("http") else f"{backend_url}{image_url}" if backend_url else image_url

        _send_restock_email(
            recipient=recipient,
            user=row.user if row.user_id else None,
            customer_name=row.name or (row.user.get_full_name() if row.user_id and row.user else "Customer"),
            product_name=row.product.name,
            product_slug=row.product.slug,
            product_image_url=product_image_url,
        )

        row.is_notified = True
        row.is_active = False
        row.save(update_fields=["is_notified", "is_active"])
        sent += 1

    stock_requests = (
        ProductStockNotifyRequest.objects.select_related("product", "variant", "user")
        .filter(product_id=product_id, is_notified=False)
        .order_by("created_at")
    )
    for row in stock_requests:
        recipient = row.email or (row.user.email if row.user_id and row.user else "")
        if not recipient:
            continue

        media = row.product.media.filter(is_primary=True).first() or row.product.media.first()
        product_image_url = ""
        if media and getattr(media, "image", None):
            image_url = str(media.image.url or "")
            backend_url = str(getattr(settings, "BACKEND_URL", "") or "").rstrip("/")
            product_image_url = image_url if image_url.startswith("http") else f"{backend_url}{image_url}" if backend_url else image_url

        _send_restock_email(
            recipient=recipient,
            user=row.user if row.user_id else None,
            customer_name=row.name or (row.user.get_full_name() if row.user_id and row.user else "Customer"),
            product_name=row.product.name,
            product_slug=row.product.slug,
            product_image_url=product_image_url,
        )
        row.is_notified = True
        row.save(update_fields=["is_notified", "updated_at"])
        sent += 1

    return sent


@shared_task(name="notifications.provider_health_check")
def provider_health_check_task():
    if not bool(getattr(settings, "NOTIFICATION_HEALTHCHECK_ENABLED", True)):
        return 0

    from .services.provider_health_service import get_provider_status_summary, test_provider

    providers = get_provider_status_summary()
    checked = 0
    for provider in providers:
        test_provider(provider)
        checked += 1
    return checked


@shared_task(name="notifications.retry_failed_logs")
def retry_failed_logs_task():
    from .models import NotificationLog, NotificationLogStatus
    from .services.retry_service import can_retry, retry_notification

    failed = NotificationLog.objects.filter(status=NotificationLogStatus.FAILED).order_by("-created_at")[:100]
    retried = 0
    for log in failed:
        if can_retry(log):
            try:
                retry_notification(str(log.id))
                retried += 1
            except Exception:  # noqa: BLE001
                logger.exception("retry_failed_log_error", log_id=str(log.id))
    return retried
