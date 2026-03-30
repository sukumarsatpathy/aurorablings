from django.urls import path
from . import views

app_name = "orders"

urlpatterns = [
    # ── Customer ──────────────────────────────────────────────
    path("",                          views.MyOrderListView.as_view(),    name="my-orders"),
    path("place/",                    views.PlaceOrderView.as_view(),     name="place"),
    path("<uuid:order_id>/",          views.MyOrderDetailView.as_view(),  name="detail"),
    path("<uuid:order_id>/cancel/",   views.CancelOrderView.as_view(),    name="cancel"),

    # ── Admin: listing ────────────────────────────────────────
    path("admin/",                    views.AdminOrderListView.as_view(),  name="admin-list"),
    path("admin/calculate/",          views.AdminOrderCalculateView.as_view(), name="admin-calculate"),
    path("admin/<uuid:order_id>/",    views.AdminOrderDetailView.as_view(), name="admin-detail"),
    path("admin/<uuid:order_id>/send-confirmation-email/", views.AdminOrderSendConfirmationEmailView.as_view(), name="admin-send-confirmation-email"),

    # ── Admin: lifecycle actions ──────────────────────────────
    path("admin/<uuid:order_id>/pay/",        views.MarkPaidView.as_view(),      name="mark-paid"),
    path("admin/<uuid:order_id>/ship/",       views.MarkShippedView.as_view(),   name="mark-shipped"),
    path("admin/<uuid:order_id>/deliver/",    views.MarkDeliveredView.as_view(), name="mark-delivered"),
    path("admin/<uuid:order_id>/complete/",   views.MarkCompletedView.as_view(), name="mark-completed"),
    path("admin/<uuid:order_id>/refund/",     views.MarkRefundedView.as_view(),  name="mark-refunded"),
    path("admin/<uuid:order_id>/transition/", views.GenericTransitionView.as_view(), name="transition"),
]
