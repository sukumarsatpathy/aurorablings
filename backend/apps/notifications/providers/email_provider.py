"""
Email notification provider.
Uses Django's built-in email backend (SMTP, console, SES, etc.)

Configuration (settings):
  EMAIL_HOST, EMAIL_PORT, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD
  EMAIL_USE_TLS = True
  DEFAULT_FROM_EMAIL = "Aurora Blings <noreply@aurorablings.com>"
"""
from __future__ import annotations

from django.core.mail import EmailMultiAlternatives
from django.conf import settings

from .base import BaseNotificationProvider, DeliveryResult
from ..events import NotificationChannel


class EmailProvider(BaseNotificationProvider):
    channel      = NotificationChannel.EMAIL
    display_name = "Email (Django SMTP)"

    def send(
        self,
        *,
        recipient: str,
        subject: str = "",
        body: str,
        html_body: str = "",
        metadata: dict = None,
    ) -> DeliveryResult:
        metadata = metadata or {}
        from_email = metadata.get("from_email", settings.DEFAULT_FROM_EMAIL)

        try:
            msg = EmailMultiAlternatives(
                subject=subject or "(no subject)",
                body=body,
                from_email=from_email,
                to=[recipient],
            )
            if html_body:
                msg.attach_alternative(html_body, "text/html")

            msg.send()
            return DeliveryResult(success=True, provider_ref=f"email:{recipient}")

        except Exception as exc:
            return DeliveryResult(success=False, error=str(exc))

    def is_configured(self) -> bool:
        return bool(getattr(settings, "EMAIL_HOST", None))
