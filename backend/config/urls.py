from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from apps.features.views import PublicRuntimeSettingsView

urlpatterns = [
    path("health/", include("apps.health.deploy_urls", namespace="public_health")),
    path("api/settings/public", PublicRuntimeSettingsView.as_view(), name="public-runtime-settings"),
    path("api/settings/public/", PublicRuntimeSettingsView.as_view(), name="public-runtime-settings-slash"),
    path("api/notify/", include("apps.notifications.notify_urls")),
    path("api/address/", include("apps.address.api.urls", namespace="address")),

    # ── API v1 ──────────────────────────────────────────────
    path("api/v1/", include([
        path("", include("core.urls")),
        path("system/health/", include("apps.health.urls", namespace="health")),
        path("auth/",      include("apps.accounts.urls",  namespace="accounts")),
        path("catalog/",   include("apps.catalog.urls",   namespace="catalog")),
        path("inventory/", include("apps.inventory.urls", namespace="inventory")),
        path("pricing/",   include("apps.pricing.urls",   namespace="pricing")),
        path("cart/",      include("apps.cart.urls",      namespace="cart")),
        path("orders/",    include("apps.orders.urls",    namespace="orders")),
        path("payments/",   include("apps.payments.urls",  namespace="payments")),
        path("surcharge/",  include("apps.surcharge.urls", namespace="surcharge")),
        path("returns/",       include("apps.returns.urls",        namespace="returns")),
        path("notifications/", include("apps.notifications.urls",   namespace="notifications")),
        path("admin/notifications/", include("apps.notifications.admin_urls", namespace="admin_notifications")),
        path("notify/", include("apps.notifications.notify_urls")),
        path("address/", include("apps.address.api.urls", namespace="address-v1")),
        path("features/",      include("apps.features.urls",       namespace="features")),
        path("logistics/",     include("apps.shipping.urls",       namespace="shipping")),
        path("reviews/",       include("apps.reviews.urls",        namespace="reviews")),
        path("",               include("apps.invoices.urls",       namespace="invoices")),
        path("banners/",       include("apps.banners.urls")),
        path("audit/",         include("audit.urls",               namespace="audit")),
    ])),

    # ── Health checks (django-health-check) ─────────────────
    # path("health/", include("health_check.urls")),

    # ── API schema & docs ───────────────────────────────────
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/",   SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/",  SpectacularRedocView.as_view(url_name="schema"),   name="redoc"),
]

if settings.ENABLE_DJANGO_ADMIN:
    urlpatterns = [path("admin/", admin.site.urls)] + urlpatterns

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
