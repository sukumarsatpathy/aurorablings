from __future__ import annotations

from datetime import datetime
from urllib.parse import urlparse

from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags

from apps.features import services as feature_services
from core.logging import get_logger
from .services.senders.brevo_sender import BrevoSender
from .services.senders.smtp_sender import SMTPSender

from .models import (
    EmailLog,
    EmailSettings,
    NotificationChannel,
    NotificationLog,
    NotificationLogStatus,
    NotificationProvider,
    NotificationType,
)

logger = get_logger(__name__)


def _resolve_public_logo_url() -> str:
    """
    Resolve a publicly reachable logo URL for email clients.
    Priority:
      1) branding_logo_url (Settings > Branding)
      2) branding.settings.logo_url
      3) frontend fallback /logo.png
    """
    frontend_url = str(
        feature_services.get_setting("site.frontend_url", default="https://aurorablings.com")
        or "https://aurorablings.com"
    ).rstrip("/")
    backend_url = str(
        feature_services.get_setting("site.backend_url", default=getattr(settings, "BACKEND_URL", "") or "")
        or ""
    ).rstrip("/")

    def _is_private_host(url: str) -> bool:
        host = (urlparse(url).hostname or "").lower()
        return host in {"", "localhost", "127.0.0.1", "0.0.0.0", "backend", "db", "redis"}

    logo_url = str(feature_services.get_setting("branding_logo_url", default="") or "").strip()
    if not logo_url:
        branding = feature_services.get_setting("branding.settings", default={}) or {}
        logo_url = str(branding.get("logo_url", "") or "").strip()
    if not logo_url:
        logo_url = "/logo.png"

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


def _load_email_settings() -> dict:
    """
    Preferred source: settings > notifications (AppSetting key: email.smtp).
    Fallback: EmailSettings model singleton.
    """
    smtp = feature_services.get_setting("notification.smtp", default={}) or {}
    if not smtp:
        smtp = feature_services.get_setting("email.smtp", default={}) or {}
    if smtp:
        return {
            "enabled": bool(smtp.get("enabled", False)),
            "host": str(smtp.get("host", "smtp.gmail.com") or "smtp.gmail.com").strip(),
            "port": int(smtp.get("port", 587) or 587),
            "username": str(smtp.get("username", "") or "").strip(),
            "password": str(smtp.get("password", "") or "").strip(),
            "use_tls": bool(smtp.get("use_tls", True)),
            "from_email": str(smtp.get("from_email", "Aurora Blings <no-reply@aurorablings.com>") or "Aurora Blings <no-reply@aurorablings.com>").strip(),
        }

    settings_row = EmailSettings.objects.first()
    if settings_row:
        return {
            "enabled": settings_row.enabled,
            "host": (settings_row.smtp_host or "").strip(),
            "port": settings_row.smtp_port,
            "username": (settings_row.smtp_user or "").strip(),
            "password": (settings_row.smtp_password or "").strip(),
            "use_tls": settings_row.use_tls,
            "from_email": (settings_row.from_email or "").strip(),
        }

    return {
        "enabled": False,
        "host": "smtp.gmail.com",
        "port": 587,
        "username": "",
        "password": "",
        "use_tls": True,
        "from_email": "Aurora Blings <no-reply@aurorablings.com>",
    }


def _resolve_email_provider() -> str:
    """
    Resolve provider with safe fallback:
    1) notification.delivery.provider
    2) if selected provider is disabled, auto-fallback to enabled provider
    """
    delivery = feature_services.get_setting("notification.delivery", default={}) or {}
    selected = str(delivery.get("provider", NotificationProvider.SMTP) or NotificationProvider.SMTP).strip().lower()

    smtp_cfg = _load_email_settings()
    brevo_cfg = feature_services.get_setting("notification.brevo", default={}) or {}
    smtp_enabled = bool(smtp_cfg.get("enabled", False))
    brevo_enabled = bool(brevo_cfg.get("enabled", False))

    if selected == NotificationProvider.BREVO and brevo_enabled:
        return NotificationProvider.BREVO
    if selected == NotificationProvider.SMTP and smtp_enabled:
        return NotificationProvider.SMTP

    if brevo_enabled:
        return NotificationProvider.BREVO
    if smtp_enabled:
        return NotificationProvider.SMTP

    return selected


def send_email(
    *,
    template_name: str,
    subject: str,
    context: dict,
    recipient: str,
    email_type: str = "generic",
    user=None,
) -> bool:
    html_content = ""
    text_content = ""
    selected_provider = NotificationProvider.SMTP
    try:
        html_content = render_to_string(template_name, context=context)
        text_content = strip_tags(html_content)

        selected_provider = _resolve_email_provider()

        if selected_provider == NotificationProvider.BREVO:
            send_result = BrevoSender().send(
                recipient=recipient,
                subject=subject,
                html_body=html_content,
                text_body=text_content,
            )
        else:
            cfg = _load_email_settings()
            if not cfg["enabled"]:
                raise RuntimeError("Email sending is disabled in settings.")
            if not cfg["username"] or not cfg["password"]:
                raise RuntimeError("SMTP username/password are missing in settings.")
            send_result = SMTPSender().send(
                recipient=recipient,
                subject=subject,
                html_body=html_content,
                text_body=text_content,
            )

        EmailLog.objects.create(
            user=user,
            recipient=recipient,
            email_type=email_type,
            status=EmailLog.STATUS_SENT,
            subject=subject,
        )
        NotificationLog.objects.create(
            channel=NotificationChannel.EMAIL,
            notification_type=NotificationType.WELCOME if email_type == "welcome" else NotificationType.CUSTOM,
            recipient=recipient,
            subject=subject,
            provider=send_result.provider if send_result.provider in dict(NotificationProvider.choices) else NotificationProvider.OTHER,
            status=NotificationLogStatus.SENT,
            template_name=template_name,
            rendered_context_json=context or {},
            rendered_html_snapshot=html_content,
            plain_text_snapshot=text_content,
            attempts_count=1,
            sent_at=timezone.now(),
            created_by=user if getattr(user, "is_authenticated", False) else None,
            related_object_type="email",
            related_object_id=email_type or "generic",
            success=True,
            provider_ref=send_result.provider,
            provider_message_id=send_result.provider_message_id or "",
            raw_response=send_result.raw_response or {"source": "email_service"},
        )
        logger.info("email_sent", email_type=email_type, recipient=recipient)
        return True
    except Exception as exc:  # noqa: BLE001
        EmailLog.objects.create(
            user=user,
            recipient=recipient,
            email_type=email_type,
            status=EmailLog.STATUS_FAILED,
            subject=subject,
            error_message=str(exc),
        )
        NotificationLog.objects.create(
            channel=NotificationChannel.EMAIL,
            notification_type=NotificationType.WELCOME if email_type == "welcome" else NotificationType.CUSTOM,
            recipient=recipient,
            subject=subject,
            provider=NotificationProvider.BREVO if selected_provider == NotificationProvider.BREVO else NotificationProvider.SMTP,
            status=NotificationLogStatus.FAILED,
            template_name=template_name,
            rendered_context_json=context or {},
            rendered_html_snapshot=html_content,
            plain_text_snapshot=text_content,
            error_message=str(exc),
            attempts_count=1,
            created_by=user if getattr(user, "is_authenticated", False) else None,
            related_object_type="email",
            related_object_id=email_type or "generic",
            success=False,
            provider_ref=selected_provider,
            error=str(exc),
            raw_response={"source": "email_service"},
        )
        logger.exception("email_send_failed", email_type=email_type, recipient=recipient, error=str(exc))
        return False


def send_welcome_email(user) -> bool:
    frontend_url = str(feature_services.get_setting("site.frontend_url", default="https://aurorablings.com") or "https://aurorablings.com").rstrip("/")
    context = {
        "user_name": user.first_name or "User",
        "activation_url": f"{frontend_url}/shop",
        "logo_url": _resolve_public_logo_url(),
        "year": datetime.now().year,
    }
    return send_email(
        template_name="emails/welcome.html",
        subject="Welcome to Aurora Blings",
        context=context,
        recipient=user.email,
        email_type="welcome",
        user=user,
    )
