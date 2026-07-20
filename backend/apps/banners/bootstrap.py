"""
Server-injected bootstrap fragment for the SPA shell.

GET /api/v1/banners/bootstrap-fragment/  →  text/html fragment

nginx SSI includes this into index.html's <head> (see frontend/index.html and
deploy/nginx/*). It exists to break the LCP request chain of the client-rendered
storefront: without it the hero banner image is only discovered after
HTML → JS → banners API → image (4 hops on slow 4G). With it, the browser sees

    <link rel="preload" as="image" ...>          — hero starts downloading
                                                   with the HTML itself
    <script>window.__BOOT__ = {...}</script>     — React boots without waiting
                                                   on /banners/active/ or
                                                   /features/public-settings/

Design constraints:

- This response is embedded server-side. The browser never requests it, so it
  must never be browser-cached (Cache-Control: no-store) — the copy inside a
  no-cache index.html is the only cache that matters (Redis, below).
- SSI blocks index.html delivery on this subrequest, so it has to be fast and
  it must never 500: any failure returns an empty 200 fragment and the
  frontend falls back to fetching the APIs exactly as before. nginx is
  additionally configured with ssi_silent_errors.
- The JSON is escaped for direct embedding in a <script> block (</script>
  and HTML-comment sequences cannot appear; see _script_safe_json).
"""

import json

from django.core.cache import cache
from django.http import HttpResponse
from django.views.decorators.http import require_GET

from .constants import PROMO_BANNERS_ACTIVE_CACHE_KEY
from .models import PromoBanner
from .serializers import PromoBannerSerializer

BOOTSTRAP_FRAGMENT_CACHE_KEY = "promo_banners:bootstrap_fragment"
BOOTSTRAP_FRAGMENT_TTL = 300  # match the /banners/active/ cache

# Must stay in sync with BANNER_SIZES in
# frontend/src/components/promo/PromoBannerCard/PromoBannerCard.jsx — the
# preload's imagesizes must select the same candidate the <img> will select,
# or the browser downloads two different derivatives.
BANNER_IMAGESIZES = "(max-width: 1024px) 100vw, (max-width: 1536px) 60vw, 900px"


def _script_safe_json(payload) -> str:
    """json.dumps hardened for inline <script> embedding.

    ensure_ascii (the default) keeps U+2028/U+2029 escaped; <, > and & are
    escaped so "</script>" and "<!--" can never appear in the output.
    """
    return (
        json.dumps(payload, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


def _preload_tag(first_banner: dict) -> str:
    """Preload for the LCP image (first active banner).

    Prefers the AVIF derivative set when complete — mirroring the <picture>
    logic in PromoBannerCard, which only emits the AVIF <source> when all
    three exist. Browsers that cannot decode AVIF ignore a preload with
    type="image/avif"; they simply lose the preload rather than fetching a
    wasted duplicate. href is deliberately omitted: imagesrcset-capable
    browsers don't need it, and legacy ones would preload the wrong size.
    """
    avif = [first_banner.get(f"image_avif_{s}") for s in ("small", "medium", "large")]
    webp = [
        first_banner.get("image_small"),
        first_banner.get("image_medium"),
        first_banner.get("image_large") or first_banner.get("image"),
    ]
    if all(avif):
        urls, mime = avif, ' type="image/avif"'
    elif all(webp):
        urls, mime = webp, ""
    else:
        return ""
    srcset = f"{urls[0]} 480w, {urls[1]} 768w, {urls[2]} 1200w"
    return (
        f'<link rel="preload" as="image"{mime} '
        f'imagesrcset="{srcset}" imagesizes="{BANNER_IMAGESIZES}" '
        f'fetchpriority="high">'
    )


def _build_fragment(request, include_preload: bool) -> str:
    banners = cache.get(PROMO_BANNERS_ACTIVE_CACHE_KEY)
    if banners is None:
        queryset = PromoBanner.objects.filter(is_active=True).order_by("order")
        banners = PromoBannerSerializer(
            queryset, many=True, context={"request": request}
        ).data
        cache.set(PROMO_BANNERS_ACTIVE_CACHE_KEY, banners, timeout=300)

    settings_data = {}
    try:
        from apps.features import services as feature_services

        settings_data = feature_services.get_public_settings()
        turnstile = feature_services.get_turnstile_config()
        settings_data["turnstile_enabled"] = bool(turnstile.get("enabled"))
        settings_data["turnstile_site_key"] = str(turnstile.get("site_key") or "")
    except Exception:
        # Settings are an optimisation here, not a contract — the frontend
        # falls back to /features/public-settings/ when absent.
        settings_data = None

    boot = {"banners": banners, "settings": settings_data}
    parts = []
    if include_preload and banners:
        # The LCP element is the top-left grid card on every breakpoint (see
        # PromoBannerGrid.jsx), which is selected by position — not by order.
        lcp_banner = next(
            (b for b in banners if b.get("position") == "top-left"), banners[0]
        )
        tag = _preload_tag(lcp_banner)
        if tag:
            parts.append(tag)
    parts.append(f"<script>window.__BOOT__={_script_safe_json(boot)};</script>")
    return "\n".join(parts)


@require_GET
def bootstrap_fragment(request):
    # ?uri= carries the page the visitor actually requested ($request_uri,
    # expanded by nginx SSI). The hero preload is only correct on the
    # homepage — every other route would pay a high-priority download of an
    # image it never shows. If the variable arrives unexpanded (or absent),
    # we conservatively omit the preload; __BOOT__ is still served.
    uri = request.GET.get("uri", "")
    include_preload = uri.split("?", 1)[0] in ("/", "/index.html")
    cache_key = f"{BOOTSTRAP_FRAGMENT_CACHE_KEY}:{'home' if include_preload else 'other'}"
    try:
        fragment = cache.get(cache_key)
        if fragment is None:
            fragment = _build_fragment(request, include_preload)
            cache.set(cache_key, fragment, timeout=BOOTSTRAP_FRAGMENT_TTL)
    except Exception:
        # Never fail the index.html SSI subrequest.
        fragment = ""
    response = HttpResponse(fragment, content_type="text/html; charset=utf-8")
    response["Cache-Control"] = "no-store"
    return response
