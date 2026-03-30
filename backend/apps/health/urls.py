from django.urls import path

from . import views

app_name = "health"

urlpatterns = [
    path("summary/", views.HealthSummaryView.as_view(), name="summary"),
    path("detailed/", views.HealthDetailedView.as_view(), name="detailed"),
    path("history/", views.HealthHistoryView.as_view(), name="history"),
    path("alerts/", views.HealthAlertsView.as_view(), name="alerts"),
]
