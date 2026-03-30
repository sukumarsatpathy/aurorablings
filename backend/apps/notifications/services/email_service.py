from __future__ import annotations

from dataclasses import dataclass

from django.core.mail import EmailMultiAlternatives, get_connection

from apps.features import services as feature_services
from core.logging import get_logger

logger = get_logger(__name__)


class EmailConfigError(Exception):
    pass


@dataclass
class SMTPConfig:
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


class EmailService:
    @staticmethod
    def load_smtp_config() -> SMTPConfig:
        raw = feature_services.get_setting("email.smtp", default={}) or {}
        return SMTPConfig(
            enabled=bool(raw.get("enabled", False)),
            host=str(raw.get("host", "smtp.gmail.com") or "smtp.gmail.com"),
            port=int(raw.get("port", 587) or 587),
            username=str(raw.get("username", "") or ""),
            password=str(raw.get("password", "") or ""),
            use_tls=bool(raw.get("use_tls", True)),
            use_ssl=bool(raw.get("use_ssl", False)),
            from_email=str(raw.get("from_email", "Aurora Blings <noreply@aurorablings.com>") or "Aurora Blings <noreply@aurorablings.com>"),
            reply_to=str(raw.get("reply_to", "") or ""),
            timeout=int(raw.get("timeout", 20) or 20),
        )

    @classmethod
    def send_html_email(
        cls,
        *,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str,
    ) -> dict:
        cfg = cls.load_smtp_config()
        if not cfg.enabled:
            raise EmailConfigError("email.smtp is disabled")

        if not cfg.host or not cfg.username or not cfg.password:
            raise EmailConfigError("Incomplete SMTP configuration")

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
            to=[to_email],
            reply_to=[cfg.reply_to] if cfg.reply_to else None,
            connection=connection,
        )
        if html_body:
            message.attach_alternative(html_body, "text/html")

        message.send(fail_silently=False)

        logger.info(
            "notification_email_sent",
            to_email=to_email,
            smtp_host=cfg.host,
            smtp_username=cfg.username,
        )
        return {"provider": "smtp", "host": cfg.host, "status": "sent"}
