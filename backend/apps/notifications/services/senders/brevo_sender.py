from __future__ import annotations

import json
import urllib.request

from apps.features import services as feature_services

from .base import NotificationSenderBase, SendResult


class BrevoSender(NotificationSenderBase):
    provider_key = "brevo"
    base_url = "https://api.brevo.com/v3"

    @staticmethod
    def load_config() -> dict:
        return feature_services.get_setting("notification.brevo", default={}) or {}

    def _build_headers(self, api_key: str) -> dict[str, str]:
        return {
            "accept": "application/json",
            "api-key": api_key,
            "content-type": "application/json",
        }

    def send(
        self,
        *,
        recipient: str,
        subject: str,
        html_body: str,
        text_body: str,
        cc_recipients: list[str] | None = None,
    ) -> SendResult:
        cfg = self.load_config()
        enabled = bool(cfg.get("enabled", False))
        api_key = str(cfg.get("api_key", "") or "")
        sender_email = str(cfg.get("from_email", "") or "")
        sender_name = str(cfg.get("from_name", "Aurora Blings") or "Aurora Blings")
        if not enabled:
            raise RuntimeError("Brevo provider is disabled in settings")
        if not api_key or not sender_email:
            raise RuntimeError("Brevo configuration is incomplete")

        payload = {
            "sender": {"email": sender_email, "name": sender_name},
            "to": [{"email": recipient}],
            "subject": subject,
            "htmlContent": html_body,
            "textContent": text_body,
        }
        if cc_recipients:
            payload["cc"] = [{"email": email} for email in cc_recipients]

        req = urllib.request.Request(
            f"{self.base_url}/smtp/email",
            data=json.dumps(payload).encode("utf-8"),
            headers=self._build_headers(api_key),
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=int(cfg.get("timeout", 15) or 15)) as response:  # noqa: S310
            body = json.loads(response.read().decode("utf-8") or "{}")

        return SendResult(
            provider="brevo",
            status="sent",
            provider_message_id=str(body.get("messageId", "") or ""),
            raw_response=body,
        )

    def test_connection(self) -> tuple[bool, str]:
        cfg = self.load_config()
        enabled = bool(cfg.get("enabled", False))
        api_key = str(cfg.get("api_key", "") or "")
        if not enabled:
            return False, "Brevo disabled"
        if not api_key:
            return False, "Brevo API key missing"

        req = urllib.request.Request(
            f"{self.base_url}/account",
            headers=self._build_headers(api_key),
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=int(cfg.get("timeout", 15) or 15)) as response:  # noqa: S310
                if response.status >= 400:
                    return False, f"Brevo returned HTTP {response.status}"
            return True, "Brevo API credentials verified"
        except Exception as exc:  # noqa: BLE001
            return False, str(exc)
