from django.urls import path

from audit.views import ActivityLogListView

app_name = "audit"

urlpatterns = [
    path("logs/", ActivityLogListView.as_view(), name="activity-log-list"),
]
