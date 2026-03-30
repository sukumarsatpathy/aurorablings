"""
SMS notification provider.
Abstracts Fast2SMS (India, default) / Twilio (international) / MSG91.

Configuration (settings / .env):
  SMS_PROVIDER         = "fast2sms"  | "twilio" | "msg91"
  FAST2SMS_API_KEY     = "..."
  TWILIO_ACCOUNT_SID   = "..."
  TWILIO_AUTH_TOKEN    = "..."
  TWILIO_SMS_FROM      = "+1xxxxxxxxxx"
  MSG91_AUTH_KEY       = "..."
  MSG91_SENDER_ID      = "AURORA"
  MSG91_TEMPLATE_ID    = "..."   # for DLT-registered templates (India)
"""
from __future__ import annotations
import requests
from django.conf import settings

from .base import BaseNotificationProvider, DeliveryResult
from ..events import NotificationChannel


class SMSProvider(BaseNotificationProvider):
    channel      = NotificationChannel.SMS
    display_name = "SMS (Fast2SMS / Twilio / MSG91)"

    def send(
        self,
        *,
        recipient: str,
        subject: str = "",
        body: str,
        html_body: str = "",
        metadata: dict = None,
    ) -> DeliveryResult:
        provider = getattr(settings, "SMS_PROVIDER", "fast2sms")

        if provider == "twilio":
            return self._send_twilio(recipient, body)
        if provider == "msg91":
            return self._send_msg91(recipient, body, metadata or {})
        return self._send_fast2sms(recipient, body)

    # ── Fast2SMS (India) ──────────────────────────────────────

    def _send_fast2sms(self, recipient: str, body: str) -> DeliveryResult:
        api_key = getattr(settings, "FAST2SMS_API_KEY", "")
        if not api_key:
            return DeliveryResult(success=False, error="Fast2SMS API key not configured.")

        phone = recipient.lstrip("+").lstrip("91")  # remove country code for Fast2SMS
        try:
            resp = requests.post(
                "https://www.fast2sms.com/dev/bulkV2",
                headers={"authorization": api_key},
                json={
                    "route":   "q",       # quick transactional
                    "message": body,
                    "language": "english",
                    "flash": 0,
                    "numbers": phone,
                },
                timeout=10,
            )
            data = resp.json()
            if data.get("return"):
                return DeliveryResult(
                    success=True,
                    provider_ref=data.get("request_id", ""),
                    raw_response=data,
                )
            return DeliveryResult(success=False, error=str(data.get("message", "Unknown error")), raw_response=data)
        except Exception as exc:
            return DeliveryResult(success=False, error=str(exc))

    # ── Twilio SMS ────────────────────────────────────────────

    def _send_twilio(self, recipient: str, body: str) -> DeliveryResult:
        try:
            from twilio.rest import Client
        except ImportError:
            return DeliveryResult(success=False, error="twilio package not installed.")

        sid      = getattr(settings, "TWILIO_ACCOUNT_SID", "")
        token    = getattr(settings, "TWILIO_AUTH_TOKEN", "")
        from_num = getattr(settings, "TWILIO_SMS_FROM", "")

        if not all([sid, token, from_num]):
            return DeliveryResult(success=False, error="Twilio SMS credentials not configured.")

        try:
            client = Client(sid, token)
            msg    = client.messages.create(body=body, from_=from_num, to=recipient)
            return DeliveryResult(success=True, provider_ref=msg.sid, raw_response={"status": msg.status})
        except Exception as exc:
            return DeliveryResult(success=False, error=str(exc))

    # ── MSG91 ─────────────────────────────────────────────────

    def _send_msg91(self, recipient: str, body: str, metadata: dict) -> DeliveryResult:
        auth_key    = getattr(settings, "MSG91_AUTH_KEY", "")
        sender_id   = getattr(settings, "MSG91_SENDER_ID", "AURORA")
        template_id = metadata.get("template_id") or getattr(settings, "MSG91_TEMPLATE_ID", "")

        if not auth_key:
            return DeliveryResult(success=False, error="MSG91 auth key not configured.")

        phone = recipient.lstrip("+")
        try:
            resp = requests.post(
                "https://api.msg91.com/api/v5/flow/",
                headers={"authkey": auth_key, "Content-Type": "application/json"},
                json={
                    "template_id": template_id,
                    "short_url":   "0",
                    "mobiles":     phone,
                    "VAR1":        body[:160],    # message variable
                },
                timeout=10,
            )
            data = resp.json()
            if data.get("type") == "success":
                return DeliveryResult(success=True, provider_ref=data.get("request_id", ""), raw_response=data)
            return DeliveryResult(success=False, error=str(data.get("message", data)), raw_response=data)
        except Exception as exc:
            return DeliveryResult(success=False, error=str(exc))

    def is_configured(self) -> bool:
        provider = getattr(settings, "SMS_PROVIDER", "fast2sms")
        if provider == "twilio":
            return bool(getattr(settings, "TWILIO_ACCOUNT_SID", ""))
        if provider == "msg91":
            return bool(getattr(settings, "MSG91_AUTH_KEY", ""))
        return bool(getattr(settings, "FAST2SMS_API_KEY", ""))
