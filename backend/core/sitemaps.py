from __future__ import annotations

from types import SimpleNamespace
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.db import DatabaseError
from django.http import HttpRequest, HttpResponse

from apps.catalog.models import Product
from apps.features import services as feature_services


def _is_private_host(url: str) -> bool:
    host = (urlparse(str(url or "")).hostname or "").lower()
    return host in {"", "localhost", "127.0.0.1", "0.0.0.0", "backend", "frontend", "web", "api", "db", "redis"}


def _configured_frontend_base_url() -> str:
    configured = ""
    try:
        configured = str(
            feature_services.get_setting(
                "site.frontend_url",
                default=getattr(settings, "FRONTEND_URL", "") or "",
            ) or ""
        ).strip().rstrip("/")
    except Exception:
        configured = str(getattr(settings, "FRONTEND_URL", "") or "").strip().rstrip("/")
    if configured and not _is_private_host(configured):
        return configured
    return ""


class FrontendAwareSitemap(Sitemap):
    """
    Uses the configured storefront domain for canonical sitemap URLs when available.
    Falls back to request host if a public frontend URL is not configured.
    """

    def get_urls(self, page=1, site=None, protocol=None):
        frontend_url = _configured_frontend_base_url()
        if frontend_url:
            parsed = urlparse(frontend_url)
            site = SimpleNamespace(domain=parsed.netloc or "")
            protocol = parsed.scheme or protocol or "https"
        try:
            return super().get_urls(page=page, site=site, protocol=protocol)
        except DatabaseError:
            return []


class StaticPagesSitemap(FrontendAwareSitemap):
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return [
            "/",
            "/products/",
            "/about-us/",
            "/contact-us/",
            "/terms-and-conditions/",
            "/privacy-policy/",
            "/return-and-refund-policy/",
            "/shipping-policy/",
        ]

    def location(self, item):
        return item


class ProductPagesSitemap(FrontendAwareSitemap):
    changefreq = "daily"
    priority = 0.9

    def items(self):
        try:
            return Product.published.only("slug", "updated_at").exclude(slug="")
        except DatabaseError:
            # Keep sitemap endpoint alive during transient DB issues.
            return Product.objects.none()

    def location(self, obj: Product):
        return f"/product/{obj.slug}"

    def lastmod(self, obj: Product):
        return obj.updated_at


def robots_txt_view(request: HttpRequest) -> HttpResponse:
    frontend_base = _configured_frontend_base_url() or request.build_absolute_uri("/").rstrip("/")
    sitemap_url = f"{frontend_base}/sitemap.xml"
    content = "\n".join(
        [
            "User-agent: *",
            "Allow: /",
            "Disallow: /admin/",
            "Disallow: /api/",
            f"Sitemap: {sitemap_url}",
            "",
        ]
    )
    return HttpResponse(content, content_type="text/plain")
