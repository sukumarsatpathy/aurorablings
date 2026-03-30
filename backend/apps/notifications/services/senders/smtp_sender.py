from __future__ import annotations

import smtplib
from dataclasses import dataclass

from django.core.mail import EmailMultiAlternatives, get_connection

from apps.features import services as feature_services

from .base import NotificationSenderBase, SendResult


@dataclass
class SmtpRuntimeConfig:
    enabled: bool
    host: str
    port: int
    username: str
    password: str
    use_tls: bool
    use_ssl: bool
    from_email: str
    reply_to: str
    timeout: int


class SMTPSender(NotificationSenderBase):
    provider_key = "smtp"

    @staticmethod
    def load_config() -> SmtpRuntimeConfig:
        raw = feature_services.get_setting("notification.smtp", default={}) or {}
        if not raw:
            raw = feature_services.get_setting("email.smtp", default={}) or {}
        return SmtpRuntimeConfig(
            enabled=bool(raw.get("enabled", False)),
            host=str(raw.get("host", "smtp.gmail.com") or "smtp.gmail.com").strip(),
            port=int(raw.get("port", 587) or 587),
            username=str(raw.get("username", "") or "").strip(),
            password=str(raw.get("password", "") or "").strip(),
            use_tls=bool(raw.get("use_tls", True)),
            use_ssl=bool(raw.get("use_ssl", False)),
            from_email=str(raw.get("from_email", "Aurora Blings <no-reply@aurorablings.com>") or "Aurora Blings <no-reply@aurorablings.com>").strip(),
            reply_to=str(raw.get("reply_to", "") or "").strip(),
            timeout=int(raw.get("timeout", 20) or 20),
        )

    def send(self, *, recipient: str, subject: str, html_body: str, text_body: str) -> SendResult:
        cfg = self.load_config()
        if not cfg.enabled:
            raise RuntimeError("SMTP provider is disabled in settings")
        if not cfg.host or not cfg.username or not cfg.password:
            raise RuntimeError("SMTP configuration is incomplete")

        connection = get_connection(
            backend="django.core.mail.backends.smtp.EmailBackend",
            host=cfg.host,
            port=cfg.port,
            username=cfg.username,
            password=cfg.password,
            use_tls=cfg.use_tls,
            use_ssl=cfg.use_ssl,
            timeout=cfg.timeout,
            fail_silently=False,
        )

        message = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=cfg.from_email,
            to=[recipient],
            reply_to=[cfg.reply_to] if cfg.reply_to else None,
            connection=connection,
        )
        if html_body:
            message.attach_alternative(html_body, "text/html")

        message.send(fail_silently=False)
        return SendResult(provider="smtp", status="sent", raw_response={"host": cfg.host})

    def test_connection(self) -> tuple[bool, str]:
        cfg = self.load_config()
        if not cfg.enabled:
            return False, "SMTP disabled"
        if not cfg.host or not cfg.username or not cfg.password:
            return False, "SMTP config incomplete"

        try:
            if cfg.use_ssl:
                server = smtplib.SMTP_SSL(cfg.host, cfg.port, timeout=cfg.timeout)
            else:
                server = smtplib.SMTP(cfg.host, cfg.port, timeout=cfg.timeout)
            with server:
                if cfg.use_tls and not cfg.use_ssl:
                    server.starttls()
                server.login(cfg.username, cfg.password)
            return True, "SMTP connection verified"
        except Exception as exc:  # noqa: BLE001
            return False, str(exc)
