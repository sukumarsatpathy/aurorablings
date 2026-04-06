from django.urls import path

from . import views

app_name = "admin_notifications"

urlpatterns = [
    path("dashboard/", views.AdminNotificationDashboardView.as_view(), name="dashboard"),
    path("newsletter/subscribers/", views.AdminNewsletterSubscriberListView.as_view(), name="newsletter-subscribers"),
    path("newsletter/subscribers/export/", views.AdminNewsletterSubscriberExportView.as_view(), name="newsletter-subscribers-export"),
    path("logs/", views.AdminNotificationLogsView.as_view(), name="logs"),
    path("logs/<uuid:log_id>/", views.AdminNotificationLogDetailView.as_view(), name="log-detail"),
    path("logs/<uuid:log_id>/retry/", views.AdminNotificationLogRetryView.as_view(), name="log-retry"),
    path("providers/status/", views.AdminNotificationProvidersStatusView.as_view(), name="providers-status"),
    path("providers/<int:provider_id>/test/", views.AdminNotificationProviderTestView.as_view(), name="provider-test"),
    path("email-preview/test/", views.AdminNotificationEmailPreviewTestView.as_view(), name="email-preview-test"),
    path("templates/usage/", views.AdminNotificationTemplateUsageView.as_view(), name="template-usage"),
]
