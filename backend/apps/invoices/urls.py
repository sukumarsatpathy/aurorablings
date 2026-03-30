from django.urls import path

from .api.views import OrderInvoiceDownloadView, PublicOrderInvoiceDownloadView, AdminOrderInvoiceRegenerateView

app_name = "invoices"

urlpatterns = [
    path("orders/<uuid:order_id>/invoice/", OrderInvoiceDownloadView.as_view(), name="order-invoice"),
    path("orders/<uuid:order_id>/invoice/public/", PublicOrderInvoiceDownloadView.as_view(), name="order-invoice-public"),
    path("orders/admin/<uuid:order_id>/invoice/regenerate/", AdminOrderInvoiceRegenerateView.as_view(), name="order-invoice-regenerate"),
]
