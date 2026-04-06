from django.urls import path
from . import views

app_name = "notifications"

urlpatterns = [
    # ── Customer ──────────────────────────────────────────────
    path("contact-form/",              views.ContactFormNotificationView.as_view(), name="contact-form"),
    path("newsletter/",               views.NewsletterSubscriptionCreateView.as_view(), name="newsletter-subscribe"),
    path("newsletter/confirm/<uuid:token>/", views.NewsletterSubscriptionConfirmView.as_view(), name="newsletter-confirm"),
    path("newsletter/unsubscribe/<uuid:token>/", views.NewsletterSubscriptionUnsubscribeView.as_view(), name="newsletter-unsubscribe"),
    path("",                          views.MyNotificationListView.as_view(),  name="my-list"),
    path("<uuid:notif_id>/",          views.MyNotificationDetailView.as_view(), name="my-detail"),
    path("<uuid:notif_id>/retry/",    views.RetryNotificationView.as_view(),    name="retry"),

    # ── Admin ─────────────────────────────────────────────────
    path("admin/",                    views.AdminNotificationListView.as_view(), name="admin-list"),
    path("admin/trigger/",            views.AdminTriggerEventView.as_view(),     name="admin-trigger"),
    path("admin/templates/",          views.AdminTemplateListCreateView.as_view(), name="admin-templates"),
    path("admin/templates/<uuid:pk>/",views.AdminTemplateDetailView.as_view(),    name="admin-template-detail"),
    path("admin/notify-subscriptions/", views.AdminNotifySubscriptionListView.as_view(), name="admin-notify-list"),
    path("admin/notify-subscriptions/mark-notified/", views.AdminNotifySubscriptionMarkNotifiedView.as_view(), name="admin-notify-mark"),
    path("admin/notify-subscriptions/mark-all-notified/", views.AdminNotifySubscriptionMarkAllNotifiedView.as_view(), name="admin-notify-mark-all"),
    path("admin/notify-subscriptions/export/", views.AdminNotifySubscriptionExportView.as_view(), name="admin-notify-export"),
    path("admin/contact-queries/", views.AdminContactQueryListView.as_view(), name="admin-contact-query-list"),
    path("admin/contact-queries/mark-read/", views.AdminContactQueryMarkReadView.as_view(), name="admin-contact-query-mark-read"),
]
