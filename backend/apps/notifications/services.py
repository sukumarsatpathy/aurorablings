"""Backward-compatible service facade for notifications app."""
from __future__ import annotations

from django.db import transaction

from core.logging import get_logger

from .events import NotificationEvent
from .models import NotifySubscription
from .services.notification_service import NotificationService, trigger_event, resend_failed_notification

logger = get_logger(__name__)


@transaction.atomic
def create_notify_subscription(
    *,
    product,
    user=None,
    name: str = "",
    email: str = "",
    phone: str = "",
) -> tuple[NotifySubscription, bool]:
    normalized_email = (email or "").strip().lower()
    normalized_phone = (phone or "").strip()
    normalized_name = (name or "").strip()

    if user and getattr(user, "is_authenticated", False):
        if not normalized_email:
            normalized_email = (getattr(user, "email", "") or "").strip().lower()
        if not normalized_phone:
            normalized_phone = (getattr(user, "phone", "") or "").strip()
        if not normalized_name:
            normalized_name = (getattr(user, "full_name", "") or "").strip()

        subscription, created = NotifySubscription.objects.get_or_create(
            product=product,
            user=user,
            defaults={
                "name": normalized_name,
                "email": normalized_email,
                "phone": normalized_phone,
                "is_active": True,
            },
        )
    else:
        if not normalized_email:
            raise ValueError("Email is required for guest subscriptions.")
        subscription, created = NotifySubscription.objects.get_or_create(
            product=product,
            email=normalized_email,
            defaults={
                "name": normalized_name,
                "phone": normalized_phone,
                "is_active": True,
            },
        )

    if not created:
        updated_fields = []
        if normalized_name and subscription.name != normalized_name:
            subscription.name = normalized_name
            updated_fields.append("name")
        if normalized_phone and subscription.phone != normalized_phone:
            subscription.phone = normalized_phone
            updated_fields.append("phone")
        if not subscription.is_active:
            subscription.is_active = True
            updated_fields.append("is_active")
        if subscription.is_notified:
            subscription.is_notified = False
            updated_fields.append("is_notified")
        if updated_fields:
            subscription.save(update_fields=updated_fields)

    return subscription, created


@transaction.atomic
def unsubscribe_notify_subscription(*, token: str) -> bool:
    row = NotifySubscription.objects.filter(unsubscribe_token=token, is_active=True).first()
    if not row:
        return False
    row.is_active = False
    row.save(update_fields=["is_active"])
    return True


def send_notification(notification_id: str):
    return NotificationService.send_notification(notification_id=notification_id)


def retry_notification(notification_id: str):
    return resend_failed_notification(notification_id)


def notify_order_placed(order):
    trigger_event(
        event=NotificationEvent.ORDER_CREATED,
        context=_order_context(order),
        recipient_user=order.user,
        recipient_email=order.guest_email or "",
    )


def notify_order_shipped(order, *, invoice_url: str = ""):
    trigger_event(
        event=NotificationEvent.ORDER_SHIPPED,
        context={
            **_order_context(order),
            "tracking_number": order.tracking_number,
            "carrier": order.shipping_carrier,
            "invoice_url": invoice_url,
        },
        recipient_user=order.user,
        recipient_email=order.guest_email or "",
    )


def notify_order_delivered(order):
    trigger_event(
        event=NotificationEvent.ORDER_DELIVERED,
        context=_order_context(order),
        recipient_user=order.user,
        recipient_email=order.guest_email or "",
    )


def _order_context(order) -> dict:
    user = order.user
    return {
        "customer_name": user.get_full_name() if user else "Customer",
        "user_name": user.get_full_name() if user else "Customer",
        "order_number": order.order_number,
        "grand_total": str(order.grand_total),
        "currency": order.currency,
        "item_count": order.items.count(),
        "order_status": order.status,
        "tracking_number": order.tracking_number,
        "tracking_url": getattr(getattr(order, "shipment", None), "tracking_url", ""),
        "carrier": order.shipping_carrier,
    }
