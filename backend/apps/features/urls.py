from django.urls import path
from . import views

app_name = "features"

urlpatterns = [
    # ── Public ───────────────────────────────────────────────
    path("public-settings/", views.PublicSettingsView.as_view(), name="public-settings"),

    # ── Admin: App Settings ───────────────────────────────────
    path("settings/",                     views.SettingListView.as_view(),       name="settings"),
    path("settings/upload/",              views.SettingUploadView.as_view(),     name="settings-upload"),
    path("settings/bulk/",                views.SettingBulkUpdateView.as_view(), name="settings-bulk"),
    path("settings/<path:key>/",          views.SettingDetailView.as_view(),     name="settings-detail"),

    # ── Admin: Features ───────────────────────────────────────
    path("",                              views.FeatureListView.as_view(),      name="list"),
    path("<slug:code>/",                  views.FeatureDetailView.as_view(),    name="detail"),
    path("<slug:code>/enable/",           views.FeatureEnableView.as_view(),    name="enable"),
    path("<slug:code>/disable/",          views.FeatureDisableView.as_view(),   name="disable"),
    path("<slug:code>/rollout/",          views.FeatureRolloutView.as_view(),   name="rollout"),

    # ── Admin: Provider configs ───────────────────────────────
    path("<slug:code>/providers/",        views.ProviderConfigListView.as_view(), name="providers"),
    path("<slug:code>/providers/activate/",views.ProviderActivateView.as_view(), name="activate-provider"),
]
