from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core import signing
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.urls import reverse
from django.utils import timezone

from apps.features import services as feature_services

from ..models import Invoice
from .pdf_service import PDFService


@dataclass
class InvoiceComputation:
    subtotal: Decimal
    shipping: Decimal
    tax: Decimal
    discount: Decimal
    total: Decimal


class InvoiceService:
    PUBLIC_TOKEN_SALT = "invoices.public.download"
    PUBLIC_TOKEN_MAX_AGE_SECONDS = 60 * 60 * 24 * 30  # 30 days

    @classmethod
    def _current_template_signature(cls) -> str:
        try:
            template_path = Path(settings.BASE_DIR) / "templates" / "invoices" / "invoice.html"
            return hashlib.sha256(template_path.read_bytes()).hexdigest()
        except Exception:
            return ""

    @classmethod
    def _resolve_customer_name(cls, *, order) -> str:
        if not order.user:
            return order.shipping_address.get("full_name", "Customer") if order.shipping_address else "Customer"

        full_name = ""
        get_full_name = getattr(order.user, "get_full_name", None)
        if callable(get_full_name):
            full_name = (get_full_name() or "").strip()
        if not full_name:
            full_name = (getattr(order.user, "full_name", "") or "").strip()
        if not full_name:
            first = (getattr(order.user, "first_name", "") or "").strip()
            last = (getattr(order.user, "last_name", "") or "").strip()
            full_name = f"{first} {last}".strip()
        return full_name or getattr(order.user, "email", "Customer")

    @classmethod
    def _invoice_file_exists(cls, *, invoice: Invoice) -> bool:
        if not invoice.file:
            return False
        try:
            return default_storage.exists(invoice.file.name)
        except Exception:
            return False

    @classmethod
    def build_invoice_number(cls, *, order) -> str:
        return f"AB-INV-{order.order_number}"

    @classmethod
    def build_invoice_url(cls, *, order_id: str) -> str:
        return reverse("invoices:order-invoice", kwargs={"order_id": order_id})

    @classmethod
    def _public_signer(cls) -> signing.TimestampSigner:
        return signing.TimestampSigner(salt=cls.PUBLIC_TOKEN_SALT)

    @classmethod
    def build_public_download_token(cls, *, order_id: str) -> str:
        signer = cls._public_signer()
        return signer.sign(str(order_id))

    @classmethod
    def is_valid_public_download_token(cls, *, order_id: str, token: str) -> bool:
        if not token:
            return False
        signer = cls._public_signer()
        try:
            value = signer.unsign(token, max_age=cls.PUBLIC_TOKEN_MAX_AGE_SECONDS)
        except (signing.BadSignature, signing.SignatureExpired):
            return False
        return str(value) == str(order_id)

    @classmethod
    def build_public_invoice_url(cls, *, order_id: str) -> str:
        token = cls.build_public_download_token(order_id=order_id)
        base = reverse("invoices:order-invoice-public", kwargs={"order_id": order_id})
        return f"{base}?token={token}"

    @classmethod
    def build_invoice_context(cls, *, order) -> dict:
        branding = feature_services.get_setting("branding.settings", default={}) or {}
        support_email = (feature_services.get_setting("email.smtp", default={}) or {}).get("reply_to", "connect@aurorablings.com")

        items = []
        for item in order.items.all():
            items.append(
                {
                    "sku": item.sku,
                    "product_name": item.product_name,
                    "variant_name": item.variant_name,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                    "line_total": item.line_total,
                }
            )

        shipping_address = order.shipping_address or {}
        billing_address = order.billing_address or shipping_address

        return {
            "brand_name": branding.get("site_name") or "Aurora Blings",
            "brand_color": "#517b4b",
            "logo_url": branding.get("logo_url", ""),
            "branding_tagline": (
                branding.get("tagline")
                or branding.get("site_tagline")
                or branding.get("subtitle")
                or "Jewellery for every story"
            ),
            "support_email": support_email,
            "invoice_number": cls.build_invoice_number(order=order),
            "order_number": order.order_number,
            "order_date": order.placed_at or order.created_at,
            "customer_name": cls._resolve_customer_name(order=order),
            "customer_email": order.user.email if order.user else order.guest_email,
            "customer_phone": shipping_address.get("phone", ""),
            "shipping_address": shipping_address,
            "billing_address": billing_address,
            "items": items,
            "subtotal": order.subtotal,
            "shipping": order.shipping_cost,
            "tax": order.tax_amount,
            "discount": order.discount_amount,
            "total": order.grand_total,
            "currency": order.currency,
            "payment_method": order.get_payment_method_display() if order.payment_method else "-",
            "payment_status": order.payment_status,
            "order_status": order.status,
            "tracking_number": order.tracking_number,
            "shipping_carrier": order.shipping_carrier,
            "invoice_download_url": cls.build_invoice_url(order_id=str(order.id)),
        }

    @classmethod
    def get_or_generate_invoice(cls, *, order, regenerate: bool = False) -> Invoice:
        invoice, _ = Invoice.objects.get_or_create(
            order=order,
            defaults={"invoice_number": cls.build_invoice_number(order=order)},
        )

        if not invoice.invoice_number:
            invoice.invoice_number = cls.build_invoice_number(order=order)

        template_signature = cls._current_template_signature()
        if invoice.file and not regenerate and cls._invoice_file_exists(invoice=invoice):
            metadata = invoice.metadata or {}
            render_engine = str(metadata.get("render_engine", "")).lower()
            existing_signature = str(metadata.get("template_signature", ""))
            if render_engine == "weasyprint" and existing_signature and existing_signature == template_signature:
                return invoice
            regenerate = True

        context = cls.build_invoice_context(order=order)
        html = PDFService.render_invoice_html(context=context)
        pdf_bytes, render_engine = PDFService.render_pdf_from_html_with_engine(html=html)

        filename = f"{invoice.invoice_number}.pdf"
        invoice.file.save(filename, ContentFile(pdf_bytes), save=False)
        invoice.file_size = len(pdf_bytes)
        invoice.generated_at = timezone.now()
        invoice.metadata = {
            "order_number": order.order_number,
            "regenerated": bool(regenerate),
            "render_engine": render_engine,
            "template_signature": template_signature,
        }
        invoice.save()
        return invoice

    @classmethod
    def invoice_filename(cls, *, invoice: Invoice) -> str:
        return Path(invoice.file.name).name if invoice.file else f"{invoice.invoice_number}.pdf"
