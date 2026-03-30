from django.urls import path
from . import views

app_name = "returns"

urlpatterns = [
    # ── Policy (public GET, admin PATCH) ──────────────────────
    path("policy/", views.ReturnPolicyView.as_view(), name="policy"),

    # ── Customer: Returns ─────────────────────────────────────
    path("",                        views.MyReturnListView.as_view(),   name="my-returns"),
    path("<uuid:rr_id>/",           views.MyReturnDetailView.as_view(), name="my-return-detail"),

    # ── Customer: Exchanges ───────────────────────────────────
    path("exchanges/",              views.MyExchangeListView.as_view(),   name="my-exchanges"),
    path("exchanges/<uuid:exc_id>/",views.MyExchangeDetailView.as_view(), name="my-exchange-detail"),

    # ── Admin: Return listings & lifecycle ────────────────────
    path("admin/",                                    views.AdminReturnListView.as_view(),               name="admin-list"),
    path("admin/<uuid:rr_id>/",                       views.AdminReturnDetailView.as_view(),             name="admin-detail"),
    path("admin/<uuid:rr_id>/approve/",               views.AdminReturnApproveView.as_view(),            name="admin-approve"),
    path("admin/<uuid:rr_id>/reject/",                views.AdminReturnRejectView.as_view(),             name="admin-reject"),
    path("admin/<uuid:rr_id>/receive/",               views.AdminReturnReceiveView.as_view(),            name="admin-receive"),
    path("admin/<uuid:rr_id>/inspect/",               views.AdminReturnInspectView.as_view(),            name="admin-inspect"),
    path("admin/<uuid:rr_id>/reintegrate-stock/",     views.AdminReturnReintegrateView.as_view(),        name="admin-reintegrate"),
    path("admin/<uuid:rr_id>/initiate-refund/",       views.AdminReturnInitiateRefundView.as_view(),     name="admin-initiate-refund"),
    path("admin/<uuid:rr_id>/complete/",              views.AdminReturnCompleteView.as_view(),           name="admin-complete"),
    path("admin/<uuid:rr_id>/reject-inspection/",     views.AdminReturnRejectAfterInspectionView.as_view(), name="admin-reject-inspection"),

    # ── Admin: Exchange listings & lifecycle ──────────────────
    path("exchanges/admin/",                               views.AdminExchangeListView.as_view(),     name="admin-exchange-list"),
    path("exchanges/admin/<uuid:exc_id>/",                 views.AdminExchangeDetailView.as_view(),   name="admin-exchange-detail"),
    path("exchanges/admin/<uuid:exc_id>/approve/",         views.AdminExchangeApproveView.as_view(),  name="admin-exchange-approve"),
    path("exchanges/admin/<uuid:exc_id>/reject/",          views.AdminExchangeRejectView.as_view(),   name="admin-exchange-reject"),
    path("exchanges/admin/<uuid:exc_id>/receive/",         views.AdminExchangeReceiveView.as_view(),  name="admin-exchange-receive"),
    path("exchanges/admin/<uuid:exc_id>/inspect/",         views.AdminExchangeInspectView.as_view(),  name="admin-exchange-inspect"),
    path("exchanges/admin/<uuid:exc_id>/reintegrate-stock/",views.AdminExchangeReintegrateView.as_view(), name="admin-exchange-reintegrate"),
    path("exchanges/admin/<uuid:exc_id>/ship/",            views.AdminExchangeShipView.as_view(),     name="admin-exchange-ship"),
    path("exchanges/admin/<uuid:exc_id>/complete/",        views.AdminExchangeCompleteView.as_view(), name="admin-exchange-complete"),
]
