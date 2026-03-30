from __future__ import annotations

from django.http import FileResponse
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView

from apps.accounts.permissions import IsStaffOrAdmin
from apps.orders import selectors as order_selectors
from core.exceptions import NotFoundError
from core.response import success_response

from ..services.invoice_service import InvoiceService


class OrderInvoiceDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        order = order_selectors.get_order_by_id(order_id, user=request.user)
        if not order and request.user.role in {"admin", "staff"}:
            order = order_selectors.get_order_by_id(order_id)
        if not order:
            raise NotFoundError("Order not found.")

        invoice = InvoiceService.get_or_generate_invoice(order=order, regenerate=False)
        if not invoice.file:
            invoice = InvoiceService.get_or_generate_invoice(order=order, regenerate=True)
        try:
            invoice_stream = invoice.file.open("rb")
        except Exception:
            invoice = InvoiceService.get_or_generate_invoice(order=order, regenerate=True)
            invoice_stream = invoice.file.open("rb")
        response = FileResponse(
            invoice_stream,
            as_attachment=True,
            filename=InvoiceService.invoice_filename(invoice=invoice),
            content_type="application/pdf",
        )
        return response


class PublicOrderInvoiceDownloadView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, order_id):
        token = str(request.query_params.get("token", "") or "").strip()
        if not InvoiceService.is_valid_public_download_token(order_id=str(order_id), token=token):
            raise NotFoundError("Invoice link is invalid or expired.")

        order = order_selectors.get_order_by_id(order_id)
        if not order:
            raise NotFoundError("Order not found.")

        invoice = InvoiceService.get_or_generate_invoice(order=order, regenerate=False)
        if not invoice.file:
            invoice = InvoiceService.get_or_generate_invoice(order=order, regenerate=True)
        try:
            invoice_stream = invoice.file.open("rb")
        except Exception:
            invoice = InvoiceService.get_or_generate_invoice(order=order, regenerate=True)
            invoice_stream = invoice.file.open("rb")
        return FileResponse(
            invoice_stream,
            as_attachment=True,
            filename=InvoiceService.invoice_filename(invoice=invoice),
            content_type="application/pdf",
        )


class AdminOrderInvoiceRegenerateView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request, order_id):
        order = order_selectors.get_order_by_id(order_id)
        if not order:
            raise NotFoundError("Order not found.")

        invoice = InvoiceService.get_or_generate_invoice(order=order, regenerate=True)
        return success_response(
            data={
                "invoice_id": str(invoice.id),
                "invoice_number": invoice.invoice_number,
                "invoice_url": InvoiceService.build_invoice_url(order_id=str(order.id)),
            },
            message="Invoice regenerated.",
        )
