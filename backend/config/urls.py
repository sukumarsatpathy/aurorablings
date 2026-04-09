from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse, HttpResponseRedirect
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from pathlib import Path
from apps.catalog import share_views as catalog_share_views
from apps.features.views import PublicRuntimeSettingsView


def _serve_frontend_index_or_root_redirect():
    candidates = [
        Path(__file__).resolve().parents[2] / "frontend" / "dist" / "index.html",
        Path(getattr(settings, "STATIC_ROOT", "")) / "index.html",
        Path(__file__).resolve().parents[1] / "templates" / "index.html",
    ]
    for candidate in candidates:
        try:
            if candidate.exists():
                return HttpResponse(candidate.read_text(encoding="utf-8"), content_type="text/html; charset=utf-8")
        except Exception:
            continue
    return HttpResponseRedirect("/")


def spa_admin_route(request, _path: str = ""):
    return _serve_frontend_index_or_root_redirect()


urlpatterns = [
    path("product/<slug:product_ref>", catalog_share_views.product_share_view, name="product-share"),
    path("product/<slug:product_ref>/", catalog_share_views.product_share_view, name="product-share-slash"),
    path("health/", include("apps.health.deploy_urls", namespace="public_health")),
    path("api/settings/public", PublicRuntimeSettingsView.as_view(), name="public-runtime-settings"),
    path("api/settings/public/", PublicRuntimeSettingsView.as_view(), name="public-runtime-settings-slash"),
    path("api/privacy/", include(("apps.privacy.urls", "privacy"), namespace="privacy-public")),
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
        path("privacy/", include("apps.privacy.urls", namespace="privacy")),
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

spa_admin_patterns = [
    re_path(
        r"^admin/(?P<_path>(dashboard|categories|attributes|products|inventory|reviews|orders|customers|returns|coupons|banners|features|settings|shipments|notifications(?:/logs)?|newsletter|audit-logs|health|notify-requests|enquiries|tracking-settings|gtm-settings))/?$",
        spa_admin_route,
        name="spa-admin-route",
    )
]

if settings.ENABLE_DJANGO_ADMIN:
    urlpatterns = spa_admin_patterns + [path("admin/", admin.site.urls)] + urlpatterns
else:
    urlpatterns = spa_admin_patterns + urlpatterns

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
