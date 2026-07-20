from celery import shared_task
from django.core.cache import cache
from .constants import PROMO_BANNERS_ACTIVE_CACHE_KEY

@shared_task
def invalidate_promo_banner_cache():
    """
    Deletes the Redis keys derived from active banners: the API payload and
    the SSI bootstrap fragment (which embeds that payload plus the LCP
    preload tag — stale copies would preload a deleted image).
    """
    # Imported here, not at module top: tasks.py is imported by signals.py at
    # app startup, keeping this import local avoids any cycle with views.
    from .bootstrap import BOOTSTRAP_FRAGMENT_CACHE_KEY

    cache.delete(PROMO_BANNERS_ACTIVE_CACHE_KEY)
    # The fragment is cached in two variants (homepage with preload / other
    # routes without) — see bootstrap.bootstrap_fragment.
    cache.delete_many([
        f"{BOOTSTRAP_FRAGMENT_CACHE_KEY}:home",
        f"{BOOTSTRAP_FRAGMENT_CACHE_KEY}:other",
    ])
