from django.urls import path
from . import views

app_name = "payments"

urlpatterns = [
    # ── Provider discovery ────────────────────────────────────
    path("providers/",              views.ProviderListView.as_view(),       name="providers"),

    # ── Payment lifecycle ─────────────────────────────────────
    path("initiate/",               views.InitiatePaymentView.as_view(),    name="initiate"),
    path("status/<uuid:txn_id>/",   views.TransactionStatusView.as_view(),  name="status"),
    path("reconcile/",              views.ReconcilePaymentView.as_view(),    name="reconcile"),
    path("retry/",                  views.RetryPaymentView.as_view(),       name="retry"),
    path("refund/",                 views.RefundView.as_view(),             name="refund"),
    path("refunds/",                views.RefundCreateView.as_view(),       name="refund-create"),

    # ── Webhooks (provider → us) ──────────────────────────────
    path("webhook/cashfree/",       views.CashfreeWebhookView.as_view(),    name="cashfree-webhook"),
    path("webhook/<str:provider>/", views.WebhookView.as_view(),            name="webhook"),

    # ── Admin ─────────────────────────────────────────────────
    path("admin/transactions/",     views.AdminTransactionListView.as_view(), name="admin-transactions"),
    path("admin/webhooks/",         views.AdminWebhookLogView.as_view(),    name="admin-webhooks"),
]
