from django.urls import path

from . import views

app_name = "pos"

urlpatterns = [
    path("terminals/",                    views.TerminalListView.as_view(),  name="terminals"),
    path("shifts/current/",               views.CurrentShiftView.as_view(),  name="shift-current"),
    path("shifts/open/",                  views.OpenShiftView.as_view(),     name="shift-open"),
    path("shifts/<uuid:shift_id>/",       views.ShiftDetailView.as_view(),   name="shift-detail"),
    path("shifts/",                       views.ShiftHistoryView.as_view(),  name="shift-history"),
    path("shifts/<uuid:shift_id>/close/", views.CloseShiftView.as_view(),    name="shift-close"),
    path("shifts/<uuid:shift_id>/summary/", views.ShiftSummaryView.as_view(), name="shift-summary"),
    path("shifts/<uuid:shift_id>/cash-movement/", views.CashMovementView.as_view(), name="cash-movement"),
    path("shifts/<uuid:shift_id>/cash-tender/",   views.CashTenderView.as_view(),   name="cash-tender"),

    path("quote/",                        views.POSQuoteView.as_view(),          name="quote"),
    path("orders/",                       views.POSOrderCreateView.as_view(),    name="order-create"),
    path("orders/part-paid/",             views.PartPaidOrderListView.as_view(), name="part-paid"),
    path("orders/<uuid:order_id>/discount/", views.ManualDiscountView.as_view(), name="manual-discount"),
    path("orders/<uuid:order_id>/void/",  views.VoidSaleView.as_view(),          name="void-sale"),
    path("orders/<uuid:order_id>/upi/",   views.UpiCollectionView.as_view(),     name="upi-collection"),
    path("orders/<uuid:order_id>/payment-state/", views.PaymentStateView.as_view(), name="payment-state"),
]
