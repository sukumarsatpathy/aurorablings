from __future__ import annotations

from dataclasses import dataclass

from django.template import Context, Template
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from core.logging import get_logger

from ..events import NotificationEvent
from ..models import NotificationTemplate

logger = get_logger(__name__)

ALLOWED_EMAIL_TEMPLATES = {
    "emails/order_confirmation.html",
    "emails/shipping_confirmation.html",
    "emails/order_delivered.html",
    "emails/forgot_password.html",
    "emails/contact_form_notification.html",
    "emails/contact_form_acknowledgement.html",
    "emails/notify_me.html",
    "emails/restock_notification.html",
    "emails/account_blocked.html",
}

DEFAULT_TEMPLATE_MAP = {
    NotificationEvent.ORDER_CREATED: {
        "subject": "Your Aurora Blings order {{ order_number }} is confirmed",
        "template_file": "emails/order_confirmation.html",
    },
    NotificationEvent.ORDER_SHIPPED: {
        "subject": "Your order {{ order_number }} has been shipped",
        "template_file": "emails/shipping_confirmation.html",
    },
    NotificationEvent.ORDER_DELIVERED: {
        "subject": "Your order {{ order_number }} is delivered",
        "template_file": "emails/order_delivered.html",
    },
    NotificationEvent.USER_FORGOT_PASSWORD: {
        "subject": "Reset your Aurora Blings password",
        "template_file": "emails/forgot_password.html",
    },
    NotificationEvent.USER_BLOCKED: {
        "subject": "Your Aurora Blings account has been temporarily restricted",
        "template_file": "emails/account_blocked.html",
    },
    NotificationEvent.CONTACT_FORM_SUBMITTED: {
        "subject": "New Contact Form Submission 🚨",
        "template_file": "emails/contact_form_notification.html",
    },
    NotificationEvent.PRODUCT_NOTIFY_ME: {
        "subject": "You're on the list 💚 We'll notify you soon!",
        "template_file": "emails/notify_me.html",
    },
    NotificationEvent.PRODUCT_RESTOCKED: {
        "subject": "🔥 Back in stock — grab yours before it's gone!",
        "template_file": "emails/restock_notification.html",
    },
}


class TemplateResolutionError(Exception):
    pass


@dataclass
class ResolvedTemplate:
    key: str
    subject_template: str
    template_file: str


class TemplateService:
    @classmethod
    def resolve_template(cls, event_type: str) -> ResolvedTemplate:
        db_template = NotificationTemplate.objects.filter(key=event_type, is_active=True).first()
        if not db_template:
            db_template = NotificationTemplate.objects.filter(event=event_type, is_active=True).first()

        if db_template:
            template_file = (db_template.template_file or "").strip()
            subject_template = (db_template.subject_template or "").strip()
            if template_file and template_file not in ALLOWED_EMAIL_TEMPLATES:
                raise TemplateResolutionError(f"Template file '{template_file}' is not allowed")

            if template_file and subject_template:
                return ResolvedTemplate(
                    key=db_template.key or event_type,
                    subject_template=subject_template,
                    template_file=template_file,
                )

        default_entry = DEFAULT_TEMPLATE_MAP.get(event_type)
        if not default_entry:
            raise TemplateResolutionError(f"No template mapping found for event '{event_type}'")
        return ResolvedTemplate(
            key=event_type,
            subject_template=default_entry["subject"],
            template_file=default_entry["template_file"],
        )

    @classmethod
    def render_subject(cls, *, subject_template: str, context: dict) -> str:
        return Template(subject_template).render(Context(context, autoescape=True)).strip()

    @classmethod
    def render_html(cls, *, template_file: str, context: dict) -> str:
        if template_file not in ALLOWED_EMAIL_TEMPLATES:
            raise TemplateResolutionError(f"Template file '{template_file}' is not allowed")
        return render_to_string(template_file, context=context)

    @classmethod
    def render_text_fallback(cls, *, html_body: str) -> str:
        return strip_tags(html_body)
