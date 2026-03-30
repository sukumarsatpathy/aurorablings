"""
WhatsApp notification provider.
Abstracts Meta Cloud API (primary) with Twilio fallback pattern.

Configuration (settings / .env):
  WHATSAPP_PROVIDER    = "meta"  | "twilio"
  WHATSAPP_META_TOKEN  = "..."
  WHATSAPP_META_PHONE_ID = "..."
  TWILIO_ACCOUNT_SID   = "..."
  TWILIO_AUTH_TOKEN    = "..."
  TWILIO_WHATSAPP_FROM = "whatsapp:+14155238886"
"""
from __future__ import annotations
import json
import requests

from django.conf import settings

from .base import BaseNotificationProvider, DeliveryResult
from ..events import NotificationChannel


class WhatsAppProvider(BaseNotificationProvider):
    channel      = NotificationChannel.WHATSAPP
    display_name = "WhatsApp (Meta Cloud API / Twilio)"

    def send(
        self,
        *,
        recipient: str,       # phone number with country code, e.g. "+919876543210"
        subject: str = "",
        body: str,
        html_body: str = "",
        metadata: dict = None,
    ) -> DeliveryResult:
        provider = getattr(settings, "WHATSAPP_PROVIDER", "meta")

        if provider == "twilio":
            return self._send_twilio(recipient, body)
        return self._send_meta(recipient, body, metadata or {})

    # ── Meta Cloud API ────────────────────────────────────────

    def _send_meta(self, recipient: str, body: str, metadata: dict) -> DeliveryResult:
        token    = getattr(settings, "WHATSAPP_META_TOKEN", "")
        phone_id = getattr(settings, "WHATSAPP_META_PHONE_ID", "")

        if not token or not phone_id:
            return DeliveryResult(success=False, error="Meta WhatsApp credentials not configured.")

        url     = f"https://graph.facebook.com/v18.0/{phone_id}/messages"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        # Use template message if template_name is in metadata, else text
        template_name = metadata.get("template_name")
        if template_name:
            payload = {
                "messaging_product": "whatsapp",
                "to": self._clean_phone(recipient),
                "type": "template",
                "template": {
                    "name": template_name,
                    "language": {"code": metadata.get("language_code", "en_US")},
                    "components": metadata.get("components", []),
                },
            }
        else:
            payload = {
                "messaging_product": "whatsapp",
                "to": self._clean_phone(recipient),
                "type": "text",
                "text": {"preview_url": False, "body": body},
            }

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return DeliveryResult(
                success=True,
                provider_ref=data.get("messages", [{}])[0].get("id", ""),
                raw_response=data,
            )
        except Exception as exc:
            return DeliveryResult(success=False, error=str(exc))

    # ── Twilio fallback ───────────────────────────────────────

    def _send_twilio(self, recipient: str, body: str) -> DeliveryResult:
        try:
            from twilio.rest import Client
        except ImportError:
            return DeliveryResult(success=False, error="twilio package not installed.")

        sid      = getattr(settings, "TWILIO_ACCOUNT_SID", "")
        token    = getattr(settings, "TWILIO_AUTH_TOKEN", "")
        from_num = getattr(settings, "TWILIO_WHATSAPP_FROM", "")

        if not all([sid, token, from_num]):
            return DeliveryResult(success=False, error="Twilio credentials not configured.")

        try:
            client = Client(sid, token)
            msg    = client.messages.create(
                body=body,
                from_=from_num,
                to=f"whatsapp:{self._clean_phone(recipient)}",
            )
            return DeliveryResult(success=True, provider_ref=msg.sid, raw_response={"status": msg.status})
        except Exception as exc:
            return DeliveryResult(success=False, error=str(exc))

    @staticmethod
    def _clean_phone(phone: str) -> str:
        """Ensure phone starts with + and has no spaces."""
        p = phone.strip().replace(" ", "").replace("-", "")
        return p if p.startswith("+") else f"+{p}"

    def is_configured(self) -> bool:
        provider = getattr(settings, "WHATSAPP_PROVIDER", "meta")
        if provider == "meta":
            return bool(getattr(settings, "WHATSAPP_META_TOKEN", ""))
        return bool(getattr(settings, "TWILIO_ACCOUNT_SID", ""))
