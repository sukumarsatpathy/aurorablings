"""
reviews.reminders
~~~~~~~~~~~~~~~~~
A few days after an order is delivered, email the customer one link per
product they haven't reviewed yet. The link opens the product page with the
review form already open (`?review=1`).

Runs daily from Celery beat. Each order is asked at most once (ReviewReminder),
only signed-in customers' orders are included (reviews need an account), and
only orders delivered inside the window — an old order is not suddenly asked
about after this ships.
"""
from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from core.logging import get_logger
from core.media import build_media_url

from .models import ProductReview, ReviewReminder

logger = get_logger(__name__)

BATCH_SIZE = 200


def _site_url() -> str:
    from apps.features import services as feature_services

    return str(
        feature_services.get_setting("site.frontend_url", default="https://aurorablings.com")
        or "https://aurorablings.com"
    ).rstrip("/")


def _products_to_review(order) -> list[dict]:
    """Distinct, still-published products in the order that this customer hasn't reviewed."""
    reviewed = set(
        ProductReview.objects.filter(user_id=order.user_id, is_soft_deleted=False)
        .values_list("product_id", flat=True)
    )
    base = _site_url()
    products, seen = [], set()
    for item in order.items.select_related("variant__product").all():
        product = getattr(item.variant, "product", None) if item.variant_id else None
        if not product or product.id in seen or product.id in reviewed:
            continue
        if not product.is_active or product.deleted_at is not None:
            continue
        seen.add(product.id)
        primary = sorted(product.media.all(), key=lambda m: (not m.is_primary, m.sort_order))
        image = None
        if primary:
            image = build_media_url(primary[0].image_small or primary[0].image)
        products.append({
            "name": product.name,
            "url": f"{base}/product/{product.slug}?review=1",
            "image": image,
        })
    return products


def send_post_delivery_review_reminders(*, now=None, dry_run: bool = False) -> dict:
    from apps.notifications.events import NotificationEvent
    from apps.notifications.services.notification_service import trigger_event
    from apps.orders.models import Order, OrderStatus

    now = now or timezone.now()
    delay = int(getattr(settings, "REVIEW_REMINDER_DELAY_DAYS", 4))
    window = int(getattr(settings, "REVIEW_REMINDER_WINDOW_DAYS", 30))

    orders = (
        Order.objects
        .filter(
            status__in=[OrderStatus.DELIVERED, OrderStatus.COMPLETED],
            user__isnull=False,
            user__is_active=True,
            delivered_at__lte=now - timedelta(days=delay),
            delivered_at__gte=now - timedelta(days=window),
            review_reminder__isnull=True,
        )
        .select_related("user")
        .order_by("delivered_at")[:BATCH_SIZE]
    )

    sent = skipped = failed = 0
    for order in orders:
        products = _products_to_review(order)
        if dry_run:
            sent += 1 if products else 0
            skipped += 0 if products else 1
            continue

        # Claim the order first so two workers can never both email it.
        try:
            with transaction.atomic():
                ReviewReminder.objects.create(order=order, sent_at=now, products_count=len(products))
        except IntegrityError:
            continue

        if not products:
            skipped += 1
            continue

        user = order.user
        try:
            trigger_event(
                event=NotificationEvent.ORDER_REVIEW_REQUEST,
                context={
                    "customer_name": user.first_name or user.get_full_name() or "there",
                    "user_name": user.get_full_name() or user.email,
                    "order_number": order.order_number,
                    "products": products,
                    "first_product_url": products[0]["url"],
                    "shop_url": f"{_site_url()}/products",
                },
                recipient_user=user,
                recipient_email=user.email,
            )
            sent += 1
        except Exception as exc:  # noqa: BLE001
            failed += 1
            logger.exception("review_reminder_failed", order_id=str(order.id), error=str(exc))

    logger.info("review_reminders_done", sent=sent, skipped=skipped, failed=failed, dry_run=dry_run)
    return {"sent": sent, "skipped": skipped, "failed": failed, "dry_run": dry_run}
