from django.urls import path

from . import views

app_name = "pos"

urlpatterns = [
    path("terminals/",                    views.TerminalListView.as_view(),  name="terminals"),
    path("shifts/current/",               views.CurrentShiftView.as_view(),  name="shift-current"),
    path("shifts/open/",                  views.OpenShiftView.as_view(),     name="shift-open"),
    path("shifts/<uuid:shift_id>/",       views.ShiftDetailView.as_view(),   name="shift-detail"),
    path("shifts/<uuid:shift_id>/close/", views.CloseShiftView.as_view(),    name="shift-close"),
    path("shifts/<uuid:shift_id>/cash-movement/", views.CashMovementView.as_view(), name="cash-movement"),
    path("shifts/<uuid:shift_id>/cash-tender/",   views.CashTenderView.as_view(),   name="cash-tender"),
]
