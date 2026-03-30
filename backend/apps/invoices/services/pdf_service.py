from __future__ import annotations

from io import BytesIO

from django.conf import settings
from django.template.loader import render_to_string


class PDFService:
    @classmethod
    def render_invoice_html(cls, *, context: dict) -> str:
        return render_to_string("invoices/invoice.html", context=context)

    @classmethod
    def render_pdf_from_html(cls, *, html: str) -> bytes:
        pdf_bytes, _engine = cls.render_pdf_from_html_with_engine(html=html)
        return pdf_bytes

    @classmethod
    def render_pdf_from_html_with_engine(cls, *, html: str) -> tuple[bytes, str]:
        try:
            from weasyprint import HTML

            return HTML(string=html, base_url=str(settings.BASE_DIR)).write_pdf(), "weasyprint"
        except Exception as weasyprint_error:
            try:
                return cls._fallback_pdf(html), "reportlab"
            except Exception as reportlab_error:
                raise RuntimeError(
                    "PDF generation failed: neither WeasyPrint nor ReportLab is available/configured."
                ) from reportlab_error

    @classmethod
    def _fallback_pdf(cls, html: str) -> bytes:
        """Fallback using reportlab if HTML engines are unavailable."""
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas

        buffer = BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        y = height - 40
        for line in html.replace("<br>", "\n").splitlines():
            if y < 40:
                pdf.showPage()
                y = height - 40
            pdf.drawString(40, y, line[:120])
            y -= 14
        pdf.save()
        return buffer.getvalue()
