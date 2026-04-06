from __future__ import annotations

import csv
import io
import uuid
from dataclasses import dataclass
from html import escape

from django.conf import settings
from django.db import transaction
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from apps.features import services as feature_services
from core.logging import get_logger

from ..email_service import _resolve_public_logo_url
from ..models import NewsletterSubscriber
from .email_service import EmailConfigError, EmailService

logger = get_logger(__name__)


@dataclass
class SubscriptionResult:
    subscriber: NewsletterSubscriber
    created: bool
    needs_confirmation: bool
    message: str


def _frontend_url() -> str:
    return str(
        feature_services.get_setting("site.frontend_url", default="https://aurorablings.com")
        or "https://aurorablings.com"
    ).rstrip("/")


def _backend_url() -> str:
    configured = str(
        feature_services.get_setting("site.backend_url", default=getattr(settings, "BACKEND_URL", "") or "")
        or getattr(settings, "BACKEND_URL", "")
        or "http://localhost:8000"
    )
    return configured.rstrip("/")


def build_confirmation_url(token: uuid.UUID) -> str:
    return f"{_backend_url()}/api/v1/notifications/newsletter/confirm/{token}/"


def build_unsubscribe_url(token: uuid.UUID) -> str:
    return f"{_backend_url()}/api/v1/notifications/newsletter/unsubscribe/{token}/"


def build_shop_url() -> str:
    return f"{_frontend_url()}/products/"


def _send_confirmation_email(subscriber: NewsletterSubscriber) -> None:
    logo_url = _resolve_public_logo_url()
    html_body = render_to_string(
        "emails/newsletter_confirm.html",
        {
            "email": subscriber.email,
            "confirm_url": build_confirmation_url(subscriber.confirmation_token),
            "unsubscribe_url": build_unsubscribe_url(subscriber.unsubscribe_token),
            "logo_url": logo_url,
            "branding_logo_url": logo_url,
            "year": timezone.now().year,
        },
    )
    text_body = (
        "Confirm your Aurora Blings subscription.\n\n"
        f"Confirm subscription: {build_confirmation_url(subscriber.confirmation_token)}\n"
        f"Unsubscribe: {build_unsubscribe_url(subscriber.unsubscribe_token)}\n"
    )

    EmailService.send_html_email(
        to_email=subscriber.email,
        subject="Confirm your Aurora Blings subscription",
        html_body=html_body,
        text_body=text_body,
    )

    subscriber.confirmation_email_sent_at = timezone.now()
    subscriber.save(update_fields=["confirmation_email_sent_at", "updated_at"])


def _send_welcome_email(subscriber: NewsletterSubscriber) -> None:
    logo_url = _resolve_public_logo_url()
    html_body = render_to_string(
        "emails/newsletter_welcome.html",
        {
            "email": subscriber.email,
            "shop_url": build_shop_url(),
            "unsubscribe_url": build_unsubscribe_url(subscriber.unsubscribe_token),
            "logo_url": logo_url,
            "branding_logo_url": logo_url,
            "year": timezone.now().year,
        },
    )
    text_body = (
        "Welcome to Aurora Blings.\n\n"
        f"Start shopping: {build_shop_url()}\n"
        f"Unsubscribe: {build_unsubscribe_url(subscriber.unsubscribe_token)}\n"
    )

    EmailService.send_html_email(
        to_email=subscriber.email,
        subject="Welcome to Aurora Blings",
        html_body=html_body,
        text_body=text_body,
    )

    subscriber.welcome_email_sent_at = timezone.now()
    subscriber.save(update_fields=["welcome_email_sent_at", "updated_at"])


@transaction.atomic
def subscribe_email(*, email: str, source: str = "footer") -> SubscriptionResult:
    normalized_email = (email or "").strip().lower()
    normalized_source = (source or "footer").strip().lower()[:50] or "footer"

    subscriber = NewsletterSubscriber.objects.filter(email=normalized_email).first()
    if subscriber and subscriber.is_active and subscriber.is_confirmed:
        return SubscriptionResult(
            subscriber=subscriber,
            created=False,
            needs_confirmation=False,
            message="This email is already subscribed.",
        )

    created = False
    if not subscriber:
        subscriber = NewsletterSubscriber.objects.create(
            email=normalized_email,
            source=normalized_source,
        )
        created = True
    else:
        subscriber.source = normalized_source or subscriber.source
        subscriber.is_active = True
        subscriber.is_confirmed = False
        subscriber.confirmed_at = None
        subscriber.unsubscribed_at = None
        subscriber.confirmation_token = uuid.uuid4()
        subscriber.unsubscribe_token = uuid.uuid4()
        subscriber.save(
            update_fields=[
                "source",
                "is_active",
                "is_confirmed",
                "confirmed_at",
                "unsubscribed_at",
                "confirmation_token",
                "unsubscribe_token",
                "updated_at",
            ]
        )

    try:
        _send_confirmation_email(subscriber)
    except EmailConfigError as exc:
        logger.warning("newsletter_confirmation_email_skipped", email=subscriber.email, error=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.exception("newsletter_confirmation_email_failed", email=subscriber.email, error=str(exc))

    return SubscriptionResult(
        subscriber=subscriber,
        created=created,
        needs_confirmation=True,
        message="Please check your email to confirm your subscription.",
    )


@transaction.atomic
def confirm_subscription(*, token: str) -> NewsletterSubscriber | None:
    subscriber = NewsletterSubscriber.objects.filter(confirmation_token=token, is_active=True).first()
    if not subscriber:
        return None

    if not subscriber.is_confirmed:
        subscriber.is_confirmed = True
        subscriber.confirmed_at = timezone.now()
        subscriber.confirmation_token = uuid.uuid4()
        subscriber.save(update_fields=["is_confirmed", "confirmed_at", "confirmation_token", "updated_at"])

        try:
            _send_welcome_email(subscriber)
        except EmailConfigError as exc:
            logger.warning("newsletter_welcome_email_skipped", email=subscriber.email, error=str(exc))
        except Exception as exc:  # noqa: BLE001
            logger.exception("newsletter_welcome_email_failed", email=subscriber.email, error=str(exc))

    return subscriber


@transaction.atomic
def unsubscribe_email(*, token: str) -> NewsletterSubscriber | None:
    subscriber = NewsletterSubscriber.objects.filter(unsubscribe_token=token, is_active=True).first()
    if not subscriber:
        return None

    subscriber.is_active = False
    subscriber.unsubscribed_at = timezone.now()
    subscriber.save(update_fields=["is_active", "unsubscribed_at", "updated_at"])
    return subscriber


def render_result_page(*, title: str, message: str, tone: str = "success") -> str:
    return render_to_string(
        "newsletter/action_result.html",
        {
            "title": title,
            "message": message,
            "tone": tone,
            "shop_url": build_shop_url(),
            "year": timezone.now().year,
        },
    )


def export_subscribers_csv(rows) -> HttpResponse:
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="newsletter-subscribers-legacy.csv"'
    writer = csv.writer(response)
    writer.writerow(["Email", "Source", "Status", "Subscribed At", "Confirmed At", "Unsubscribed At"])
    for row in rows:
        writer.writerow(
            [
                row.email,
                row.source,
                row.status_label,
                row.subscribed_at.isoformat() if row.subscribed_at else "",
                row.confirmed_at.isoformat() if row.confirmed_at else "",
                row.unsubscribed_at.isoformat() if row.unsubscribed_at else "",
            ]
        )
    return response


def export_subscribers_excel(rows) -> HttpResponse:
    html = [
        "<table border='1'>",
        "<tr><th>Email</th><th>Source</th><th>Status</th><th>Subscribed At</th><th>Confirmed At</th><th>Unsubscribed At</th></tr>",
    ]
    for row in rows:
        html.append(
            "<tr>"
            f"<td>{escape(row.email)}</td>"
            f"<td>{escape(row.source or '')}</td>"
            f"<td>{escape(row.status_label)}</td>"
            f"<td>{escape(row.subscribed_at.isoformat() if row.subscribed_at else '')}</td>"
            f"<td>{escape(row.confirmed_at.isoformat() if row.confirmed_at else '')}</td>"
            f"<td>{escape(row.unsubscribed_at.isoformat() if row.unsubscribed_at else '')}</td>"
            "</tr>"
        )
    html.append("</table>")

    response = HttpResponse("".join(html), content_type="application/vnd.ms-excel")
    response["Content-Disposition"] = 'attachment; filename="newsletter-subscribers.xls"'
    return response


def export_subscribers_pdf(rows) -> HttpResponse:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 0.75 * inch

    pdf.setFillColor(colors.HexColor("#22311f"))
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(0.75 * inch, y, "Aurora Blings Newsletter Subscribers")
    y -= 0.3 * inch

    pdf.setFont("Helvetica", 9)
    pdf.setFillColor(colors.HexColor("#556553"))
    pdf.drawString(0.75 * inch, y, f"Generated at: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}")
    y -= 0.35 * inch

    headers = ["Email", "Source", "Status", "Subscribed"]
    column_x = [0.75 * inch, 3.4 * inch, 4.6 * inch, 5.8 * inch]

    def draw_header():
        nonlocal y
        pdf.setFillColor(colors.HexColor("#517b4b"))
        pdf.rect(0.65 * inch, y - 0.18 * inch, width - 1.3 * inch, 0.28 * inch, fill=1, stroke=0)
        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 9)
        for header, x in zip(headers, column_x):
            pdf.drawString(x, y - 0.02 * inch, header)
        y -= 0.3 * inch

    draw_header()

    for row in rows:
        if y < 1.0 * inch:
            pdf.showPage()
            y = height - 0.75 * inch
            draw_header()

        pdf.setFillColor(colors.HexColor("#22311f"))
        pdf.setFont("Helvetica", 8)
        subscribed_value = row.subscribed_at.strftime("%Y-%m-%d") if row.subscribed_at else ""
        values = [row.email, row.source, row.status_label, subscribed_value]

        for value, x in zip(values, column_x):
            truncated = value
            while stringWidth(truncated, "Helvetica", 8) > 150 and len(truncated) > 4:
                truncated = f"{truncated[:-4]}..."
            pdf.drawString(x, y, truncated)
        y -= 0.22 * inch

    pdf.save()
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="newsletter-subscribers.pdf"'
    return response
