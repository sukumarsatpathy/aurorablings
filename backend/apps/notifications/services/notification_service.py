from __future__ import annotations

from datetime import datetime
from urllib.parse import urlparse

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.features import services as feature_services
from core.logging import get_logger

from ..events import NotificationChannel
from ..models import (
    Notification,
    NotificationAttempt,
    NotificationLog,
    NotificationLogStatus,
    NotificationProvider,
    NotificationStatus,
    NotificationType,
)
from .senders.base import NotificationSenderBase
from .senders.brevo_sender import BrevoSender
from .senders.smtp_sender import SMTPSender
from .template_service import TemplateResolutionError, TemplateService

logger = get_logger(__name__)


DEFAULT_NOTIFICATION_SETTINGS = {
    "email_enabled": True,
    "queue_enabled": True,
    "log_failures": True,
    "max_retries": int(getattr(settings, "NOTIFICATION_MAX_RETRY", 3)),
}


def get_notification_settings() -> dict:
    raw = feature_services.get_setting("notifications.settings", default={}) or {}
    data = {**DEFAULT_NOTIFICATION_SETTINGS, **raw}
    return data


def get_event_settings() -> dict:
    return feature_services.get_setting("notifications.events", default={}) or {}


def is_event_enabled(event_type: str) -> bool:
    events = get_event_settings()
    if not events:
        return True
    return bool((events.get(event_type) or {}).get("enabled", False))


def map_event_to_type(event_type: str) -> str:
    normalized = (event_type or "").lower()
    if "welcome" in normalized:
        return NotificationType.WELCOME
    if "order" in normalized and ("created" in normalized or "confirmed" in normalized):
        return NotificationType.ORDER_CONFIRMED
    if "password" in normalized or "reset" in normalized:
        return NotificationType.RESET_PASSWORD
    if "shipped" in normalized or "shipping" in normalized:
        return NotificationType.SHIPPING_UPDATE
    if "refund" in normalized:
        return NotificationType.REFUND
    if "contact" in normalized:
        return NotificationType.CONTACT
    if "notify" in normalized or "stock" in normalized:
        return NotificationType.PRODUCT_NOTIFY
    return NotificationType.CUSTOM


def get_active_sender() -> NotificationSenderBase:
    delivery = feature_services.get_setting("notification.delivery", default={}) or {}
    provider = str(delivery.get("provider", NotificationProvider.SMTP) or NotificationProvider.SMTP).lower().strip()

    smtp_cfg = feature_services.get_setting("notification.smtp", default={}) or {}
    if not smtp_cfg:
        smtp_cfg = feature_services.get_setting("email.smtp", default={}) or {}
    brevo_cfg = feature_services.get_setting("notification.brevo", default={}) or {}

    smtp_enabled = bool(smtp_cfg.get("enabled", False))
    brevo_enabled = bool(brevo_cfg.get("enabled", False))

    if provider == NotificationProvider.BREVO and brevo_enabled:
        return BrevoSender()
    if provider == NotificationProvider.SMTP and smtp_enabled:
        return SMTPSender()

    # Fallback to whichever provider is actually active in settings.
    if brevo_enabled:
        return BrevoSender()
    if smtp_enabled:
        return SMTPSender()

    return SMTPSender()


def _resolve_logo_url(frontend_url: str, backend_url: str) -> str:
    logo_url = str(feature_services.get_setting("branding_logo_url", default="") or "").strip()
    if not logo_url:
        branding = feature_services.get_setting("branding.settings", default={}) or {}
        logo_url = str(branding.get("logo_url", "") or "").strip()
    if not logo_url:
        logo_url = "/logo.png"

    def _is_private_host(url: str) -> bool:
        host = (urlparse(url).hostname or "").lower()
        return host in {"", "localhost", "127.0.0.1", "0.0.0.0", "backend", "db", "redis"}

    if logo_url.startswith("http://") or logo_url.startswith("https://"):
        if not _is_private_host(logo_url):
            return logo_url
        logo_url = "/logo.png"

    if logo_url.startswith("/"):
        if backend_url and not _is_private_host(backend_url):
            return f"{backend_url}{logo_url}"
        if frontend_url and not _is_private_host(frontend_url):
            return f"{frontend_url}{logo_url}"
        return f"https://aurorablings.com{logo_url}"
    if frontend_url and not _is_private_host(frontend_url):
        return f"{frontend_url}/{logo_url.lstrip('/')}"
    return f"https://aurorablings.com/{logo_url.lstrip('/')}"


def _is_private_host(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host in {"", "localhost", "127.0.0.1", "0.0.0.0", "backend", "db", "redis"}


def _to_absolute_url(raw_url: str, *, frontend_url: str, backend_url: str) -> str:
    value = str(raw_url or "").strip()
    if not value:
        return value
    if value.startswith(("mailto:", "tel:", "#")):
        return value

    fallback = "https://aurorablings.com"
    web_base = frontend_url or backend_url or fallback
    api_base = backend_url or frontend_url or fallback

    parsed = urlparse(value)
    if parsed.scheme in {"http", "https"}:
        return value

    if value.startswith("/"):
        base = api_base if value.startswith("/api/") else web_base
        return f"{base}{value}"

    if value.startswith("api/"):
        return f"{api_base}/{value}"

    return f"{web_base}/{value.lstrip('/')}"


def _normalized_email_list(value) -> list[str]:
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, (list, tuple, set)):
        values = list(value)
    else:
        values = []
    seen: set[str] = set()
    output: list[str] = []
    for raw in values:
        email = str(raw or "").strip().lower()
        if not email or "@" not in email or email in seen:
            continue
        seen.add(email)
        output.append(email)
    return output


def _build_cc_recipients(*, event_type: str, context: dict, primary_recipient: str) -> list[str]:
    cc_list = _normalized_email_list((context or {}).get("cc_emails"))
    if str(event_type or "").strip().lower() == "order.created":
        cc_list = _normalized_email_list(cc_list + ["connect@aurorablings.com"])
    primary = str(primary_recipient or "").strip().lower()
    return [email for email in cc_list if email != primary]


def _build_template_context(raw_context: dict, event_type: str) -> dict:
    context = dict(raw_context or {})
    frontend_url = str(
        feature_services.get_setting("site.frontend_url", default="https://aurorablings.com")
        or "https://aurorablings.com"
    ).rstrip("/")
    backend_url = str(
        feature_services.get_setting("site.backend_url", default=getattr(settings, "BACKEND_URL", "") or "")
        or ""
    ).rstrip("/")
    support_email = str((feature_services.get_setting("notification.smtp", default={}) or {}).get("reply_to", "")).strip()
    support_url = str(feature_services.get_setting("site.support_url", default=f"{frontend_url}/contact-us") or f"{frontend_url}/contact-us").strip()

    context.setdefault("event_type", event_type)
    context.setdefault("year", datetime.now().year)
    context.setdefault("site_url", frontend_url)
    context.setdefault("support_url", support_url)
    context.setdefault("support_email", support_email or "connect@aurorablings.com")
    context.setdefault("logo_url", _resolve_logo_url(frontend_url=frontend_url, backend_url=backend_url))

    customer_name = str(context.get("customer_name") or context.get("user_name") or "").strip()
    if customer_name and not context.get("user"):
        context["user"] = {"first_name": customer_name.split(" ")[0] if customer_name else "Customer"}

    product_name = str(context.get("product_name") or "").strip()
    if product_name and not context.get("product"):
        context["product"] = {
            "name": product_name,
            "image_url": context.get("product_image_url", ""),
            "price": context.get("product_price", ""),
        }

    if context.get("unlock_time") and not context.get("blocked_until"):
        context["blocked_until"] = context["unlock_time"]
    if context.get("order_number") and not context.get("order_id"):
        context["order_id"] = context["order_number"]
    if context.get("grand_total") and not context.get("total"):
        context["total"] = context["grand_total"]
    if context.get("shipping_cost") and not context.get("shipping"):
        context["shipping"] = context["shipping_cost"]

    for url_key in [
        "invoice_url",
        "order_url",
        "tracking_url",
        "activation_url",
        "unsubscribe_url",
        "reset_url",
        "support_url",
        "site_url",
        "logo_url",
    ]:
        if context.get(url_key):
            context[url_key] = _to_absolute_url(
                str(context[url_key]),
                frontend_url=frontend_url,
                backend_url=backend_url,
            )

    product = context.get("product")
    if isinstance(product, dict) and product.get("image_url"):
        product["image_url"] = _to_absolute_url(
            str(product["image_url"]),
            frontend_url=frontend_url,
            backend_url=backend_url,
        )

    return context


def render_template(*, event_type: str, context: dict) -> dict:
    template = TemplateService.resolve_template(event_type)
    merged_context = _build_template_context(raw_context=context, event_type=event_type)
    subject = TemplateService.render_subject(subject_template=template.subject_template, context=merged_context)
    html_body = TemplateService.render_html(template_file=template.template_file, context=merged_context)
    text_body = TemplateService.render_text_fallback(html_body=html_body)
    return {
        "template": template,
        "subject": subject,
        "html_body": html_body,
        "text_body": text_body,
        "context": merged_context,
    }


def create_log_entry(
    *,
    notification: Notification,
    recipient: str,
    subject: str,
    template_name: str,
    rendered_context_json: dict,
    rendered_html_snapshot: str,
    plain_text_snapshot: str,
    provider: str,
    notification_type: str,
) -> NotificationLog:
    attempt_no = notification.retry_count + 1
    return NotificationLog.objects.create(
        notification=notification,
        attempt_number=attempt_no,
        success=False,
        provider_ref=provider,
        raw_response={},
        channel=notification.channel,
        notification_type=notification_type,
        recipient=recipient,
        subject=subject,
        provider=provider,
        status=NotificationLogStatus.PENDING,
        template_name=template_name,
        rendered_context_json=rendered_context_json,
        rendered_html_snapshot=rendered_html_snapshot,
        plain_text_snapshot=plain_text_snapshot,
        attempts_count=attempt_no,
        created_by=notification.user,
        related_object_type="notification",
        related_object_id=str(notification.id),
    )


def update_log_success(*, log_entry: NotificationLog, provider_response: dict, provider_message_id: str = "") -> NotificationLog:
    now = timezone.now()
    log_entry.success = True
    log_entry.status = NotificationLogStatus.SENT
    log_entry.sent_at = now
    log_entry.last_attempt_at = now
    log_entry.provider_message_id = provider_message_id
    log_entry.provider_ref = log_entry.provider
    log_entry.raw_response = provider_response or {}
    log_entry.error = ""
    log_entry.error_message = ""
    log_entry.error_code = ""
    log_entry.save(
        update_fields=[
            "success",
            "status",
            "sent_at",
            "last_attempt_at",
            "provider_message_id",
            "provider_ref",
            "raw_response",
            "error",
            "error_message",
            "error_code",
        ]
    )
    return log_entry


def update_log_failure(*, log_entry: NotificationLog, error_message: str, error_code: str = "", provider_response: dict | None = None) -> NotificationLog:
    now = timezone.now()
    log_entry.success = False
    log_entry.status = NotificationLogStatus.FAILED
    log_entry.last_attempt_at = now
    log_entry.error = error_message
    log_entry.error_message = error_message
    log_entry.error_code = error_code
    log_entry.raw_response = provider_response or {}
    log_entry.save(update_fields=["success", "status", "last_attempt_at", "error", "error_message", "error_code", "raw_response"])
    return log_entry


@transaction.atomic
def create_notification(
    *,
    event_type: str,
    payload: dict,
    user=None,
    email: str = "",
    channel: str = NotificationChannel.EMAIL,
    send_async: bool = True,
) -> Notification:
    settings_payload = get_notification_settings()
    resolved_email = (email or "").strip() or (getattr(user, "email", "") if user else "")

    status = NotificationStatus.PENDING
    error_message = ""

    if channel != NotificationChannel.EMAIL:
        status = NotificationStatus.SKIPPED
        error_message = f"Channel '{channel}' is not implemented yet."
    elif not settings_payload.get("email_enabled", True):
        status = NotificationStatus.SKIPPED
        error_message = "Email notifications are disabled."
    elif not is_event_enabled(event_type):
        status = NotificationStatus.SKIPPED
        error_message = f"Event '{event_type}' is disabled in settings."
    elif not resolved_email:
        status = NotificationStatus.SKIPPED
        error_message = "No recipient email available."

    notification = Notification.objects.create(
        user=user,
        email=resolved_email,
        event_type=event_type,
        channel=channel,
        status=status,
        payload=payload or {},
        error_message=error_message,
        subject_snapshot="",
        template_key=event_type,
        event=event_type,
        recipient_email=resolved_email,
        context_data=payload or {},
        max_retries=int(settings_payload.get("max_retries", getattr(settings, "NOTIFICATION_MAX_RETRY", 3)) or 3),
        last_error=error_message,
    )

    if notification.status == NotificationStatus.PENDING:
        if send_async and settings_payload.get("queue_enabled", True):
            from ..tasks import send_notification_task

            send_notification_task.delay(str(notification.id))
        else:
            send_notification(notification_id=str(notification.id))

    return notification


@transaction.atomic
def send_notification(*, notification_id: str) -> Notification | None:
    notification = Notification.objects.filter(id=notification_id).first()
    if not notification:
        logger.warning("notification_not_found", notification_id=notification_id)
        return None

    if notification.status in {NotificationStatus.SENT, NotificationStatus.SKIPPED}:
        return notification

    attempt_no = notification.retry_count + 1

    try:
        rendered = render_template(
            event_type=notification.event_type or notification.event,
            context=dict(notification.payload or notification.context_data or {}),
        )
        template = rendered["template"]
        subject = rendered["subject"]
        html_body = rendered["html_body"]
        text_body = rendered["text_body"]
        context = rendered["context"]

        recipient = notification.email or notification.recipient_email
        sender = get_active_sender()
        log_entry = create_log_entry(
            notification=notification,
            recipient=recipient,
            subject=subject,
            template_name=template.key or template.code or template.template_file,
            rendered_context_json=context,
            rendered_html_snapshot=html_body,
            plain_text_snapshot=text_body,
            provider=sender.provider_key,
            notification_type=map_event_to_type(notification.event_type or notification.event),
        )

        send_result = sender.send(
            recipient=recipient,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            cc_recipients=_build_cc_recipients(
                event_type=notification.event_type or notification.event,
                context=context,
                primary_recipient=recipient,
            ),
        )

        notification.status = NotificationStatus.SENT
        notification.sent_at = timezone.now()
        notification.error_message = ""
        notification.subject_snapshot = subject
        notification.template_key = template.key or template.code or (notification.event_type or notification.event)

        notification.subject = subject
        notification.body = text_body
        notification.html_body = html_body
        notification.last_error = ""
        notification.provider_ref = send_result.provider

        NotificationAttempt.objects.create(
            notification=notification,
            attempt_no=attempt_no,
            status=NotificationStatus.SENT,
            provider_response=send_result.raw_response or {},
        )
        update_log_success(
            log_entry=log_entry,
            provider_response=send_result.raw_response or {},
            provider_message_id=send_result.provider_message_id,
        )

    except (TemplateResolutionError, RuntimeError) as exc:
        notification.status = NotificationStatus.FAILED
        notification.error_message = str(exc)
        notification.last_error = str(exc)
        notification.retry_count += 1

        NotificationAttempt.objects.create(
            notification=notification,
            attempt_no=attempt_no,
            status=NotificationStatus.FAILED,
            error_message=str(exc),
            provider_response={},
        )

        NotificationLog.objects.create(
            notification=notification,
            attempt_number=attempt_no,
            success=False,
            provider_ref=notification.provider_ref,
            error=str(exc),
            raw_response={},
            channel=notification.channel,
            notification_type=map_event_to_type(notification.event_type or notification.event),
            recipient=notification.email or notification.recipient_email,
            subject=notification.subject_snapshot or notification.subject,
            provider=notification.provider_ref or NotificationProvider.SMTP,
            status=NotificationLogStatus.FAILED,
            template_name=notification.template_key,
            rendered_context_json=dict(notification.payload or {}),
            rendered_html_snapshot=notification.html_body or "",
            plain_text_snapshot=notification.body or "",
            error_message=str(exc),
            attempts_count=attempt_no,
            last_attempt_at=timezone.now(),
            created_by=notification.user,
            related_object_type="notification",
            related_object_id=str(notification.id),
        )
        logger.warning("notification_send_failed", notification_id=notification_id, error=str(exc))
    except Exception as exc:  # noqa: BLE001
        notification.status = NotificationStatus.FAILED
        notification.error_message = "Unexpected notification send failure"
        notification.last_error = str(exc)
        notification.retry_count += 1

        NotificationAttempt.objects.create(
            notification=notification,
            attempt_no=attempt_no,
            status=NotificationStatus.FAILED,
            error_message=str(exc),
            provider_response={},
        )

        NotificationLog.objects.create(
            notification=notification,
            attempt_number=attempt_no,
            success=False,
            provider_ref=notification.provider_ref,
            error=str(exc),
            raw_response={},
            channel=notification.channel,
            notification_type=map_event_to_type(notification.event_type or notification.event),
            recipient=notification.email or notification.recipient_email,
            subject=notification.subject_snapshot or notification.subject,
            provider=notification.provider_ref or NotificationProvider.SMTP,
            status=NotificationLogStatus.FAILED,
            template_name=notification.template_key,
            rendered_context_json=dict(notification.payload or {}),
            rendered_html_snapshot=notification.html_body or "",
            plain_text_snapshot=notification.body or "",
            error_message=str(exc),
            error_code="unexpected_error",
            attempts_count=attempt_no,
            last_attempt_at=timezone.now(),
            created_by=notification.user,
            related_object_type="notification",
            related_object_id=str(notification.id),
        )
        logger.exception("notification_send_unexpected_error", notification_id=notification_id)

    notification.save(
        update_fields=[
            "status",
            "sent_at",
            "error_message",
            "subject_snapshot",
            "template_key",
            "subject",
            "body",
            "html_body",
            "last_error",
            "provider_ref",
            "retry_count",
            "updated_at",
        ]
    )
    return notification


def send_email_notification(*, event_type: str, recipient: str, payload: dict, user=None, send_async: bool = True) -> Notification:
    return create_notification(
        event_type=event_type,
        payload=payload,
        user=user,
        email=recipient,
        channel=NotificationChannel.EMAIL,
        send_async=send_async,
    )


def resend_failed_notification(*, notification_id: str) -> Notification | None:
    notification = Notification.objects.filter(id=notification_id).first()
    if not notification:
        return None

    if notification.status != NotificationStatus.FAILED:
        return notification

    if notification.retry_count >= notification.max_retries:
        return notification

    notification.status = NotificationStatus.PENDING
    notification.save(update_fields=["status", "updated_at"])

    from ..tasks import send_notification_task

    send_notification_task.delay(str(notification.id))
    return notification


class NotificationService:
    get_notification_settings = staticmethod(get_notification_settings)
    get_event_settings = staticmethod(get_event_settings)
    is_event_enabled = staticmethod(is_event_enabled)
    create_notification = staticmethod(create_notification)
    send_notification = staticmethod(send_notification)
    resend_failed_notification = staticmethod(resend_failed_notification)



def trigger_event(
    *,
    event: str,
    context: dict,
    recipient_user=None,
    recipient_email: str = "",
    recipient_phone: str = "",
    send_at=None,
    channels: list[str] | None = None,
):
    del recipient_phone, send_at
    selected_channels = channels or [NotificationChannel.EMAIL]
    notifications = []
    for channel in selected_channels:
        notifications.append(
            create_notification(
                event_type=event,
                payload=context or {},
                user=recipient_user,
                email=recipient_email,
                channel=channel,
                send_async=True,
            )
        )
    return notifications



def resend_failed_notification_by_id(notification_id: str):
    return resend_failed_notification(notification_id=notification_id)
