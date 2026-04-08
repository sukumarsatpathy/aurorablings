from __future__ import annotations

from urllib.parse import urlparse

from django.conf import settings
from django.shortcuts import render

from apps.features import services as feature_services
from core.exceptions import NotFoundError
from core.media import build_media_url

from . import selectors


def _is_private_host(url: str) -> bool:
    host = (urlparse(str(url or "")).hostname or "").lower()
    return host in {"", "localhost", "127.0.0.1", "0.0.0.0", "backend", "frontend", "web", "api", "db", "redis"}


def _resolve_frontend_base_url(request) -> str:
    configured = str(
        feature_services.get_setting(
            "site.frontend_url",
            default=getattr(settings, "FRONTEND_URL", "") or "",
        ) or ""
    ).rstrip("/")
    if configured and not _is_private_host(configured):
        return configured
    return request.build_absolute_uri("/").rstrip("/")


def _product_share_target_url(*, request, product) -> str:
    frontend_base = _resolve_frontend_base_url(request)
    return f"{frontend_base}/product/{product.slug or product.id}"


def _product_share_image_url(*, request, product) -> str:
    media = product.media.filter(is_primary=True).first() or product.media.first()
    if media and getattr(media, "image", None):
        return build_media_url(media.image, request=request) or ""
    return ""


def product_share_view(request, product_ref: str):
    product = selectors.get_product_by_slug(product_ref, published_only=True)
    if not product:
        product = selectors.get_product_by_id(product_ref, published_only=True)
    if not product:
        raise NotFoundError("Product not found.")

    title = (product.meta_title or product.name or "Aurora Blings").strip()
    description = (
        product.meta_description
        or product.short_description
        or product.description
        or "Discover premium jewellery from Aurora Blings."
    )
    description = " ".join(str(description).replace("\n", " ").split()).strip()
    if len(description) > 180:
        description = f"{description[:179].rstrip()}..."

    share_url = _product_share_target_url(request=request, product=product)
    image_url = _product_share_image_url(request=request, product=product)
    branding = feature_services.get_setting("branding.settings", default={}) or {}

    return render(
        request,
        "sharing/product_share.html",
        {
            "title": title,
            "description": description,
            "image_url": image_url,
            "image_alt": product.name,
            "share_url": share_url,
            "site_name": branding.get("site_name") or "Aurora Blings",
            "brand_name": branding.get("site_name") or "Aurora Blings",
            "product": product,
        },
    )
