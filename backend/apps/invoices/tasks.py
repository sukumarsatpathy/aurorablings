from celery import shared_task


@shared_task(name="invoices.generate_invoice")
def generate_invoice_task(order_id: str):
    from apps.orders.selectors import get_order_by_id
    from .services.invoice_service import InvoiceService

    order = get_order_by_id(order_id)
    if not order:
        return None
    invoice = InvoiceService.get_or_generate_invoice(order=order, regenerate=False)
    return str(invoice.id)
