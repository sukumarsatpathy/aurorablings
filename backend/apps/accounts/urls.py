from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

app_name = "accounts"

urlpatterns = [
    # ── Auth ─────────────────────────────────────────────────
    path("register/",        views.RegisterView.as_view(),             name="register"),
    path("login/",           views.LoginView.as_view(),                name="login"),
    path("logout/",          views.LogoutView.as_view(),               name="logout"),
    path("token/refresh/",   TokenRefreshView.as_view(),               name="token-refresh"),

    # ── Password ──────────────────────────────────────────────
    path("password/reset/",          views.PasswordResetRequestView.as_view(), name="password-reset-request"),
    path("password/reset/confirm/",  views.PasswordResetConfirmView.as_view(), name="password-reset-confirm"),
    path("password/change/",         views.ChangePasswordView.as_view(),       name="password-change"),

    # ── Profile ───────────────────────────────────────────────
    path("profile/",         views.ProfileView.as_view(),              name="profile"),

    # ── Addresses ─────────────────────────────────────────────
    path("addresses/",       views.AddressListCreateView.as_view(),    name="address-list"),
    path("addresses/<uuid:pk>/", views.AddressDetailView.as_view(),    name="address-detail"),

    # ── Admin Customers ───────────────────────────────────────
    path("admin/customers/", views.AdminCustomerListView.as_view(), name="admin-customer-list"),
    path("admin/customers/<uuid:pk>/", views.AdminCustomerDetailView.as_view(), name="admin-customer-detail"),
    path("admin/customers/<uuid:pk>/send-welcome-email/", views.AdminCustomerSendWelcomeEmailView.as_view(), name="admin-customer-send-welcome-email"),
    path("admin/customers/<uuid:pk>/unblock/", views.AdminCustomerUnblockView.as_view(), name="admin-customer-unblock"),
    path("admin/customers/<uuid:user_id>/addresses/", views.AdminAddressListCreateView.as_view(), name="admin-customer-address-list"),
    path("admin/customers/<uuid:user_id>/addresses/<uuid:pk>/", views.AdminAddressDetailView.as_view(), name="admin-customer-address-detail"),
]
