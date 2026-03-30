from celery import shared_task
from django.core.cache import cache
from .constants import PROMO_BANNERS_ACTIVE_CACHE_KEY

@shared_task
def invalidate_promo_banner_cache():
    """
    Deletes the Redis key for active banners.
    """
    cache.delete(PROMO_BANNERS_ACTIVE_CACHE_KEY)
