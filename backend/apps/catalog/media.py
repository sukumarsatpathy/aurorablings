"""Picking the right photo for a variant."""

from __future__ import annotations


def media_tag_ids(media) -> set:
    """The option ids a photo is tagged with (prefetch `attribute_values`)."""
    return {av.pk for av in media.attribute_values.all()}


def variant_photo(variant, media_items):
    """
    The photo that shows this variant.

    Photos can be tagged with options (Products → image → one pick per
    attribute, e.g. Color: Violet, or Color: Violet + Size: 2-6). A photo
    fits a variant when the variant has every option the photo is tagged
    with. Of the fitting photos the most specific win (Violet + 2-6 beats
    Violet alone), then the primary, then the first by sort order. A variant
    no tagged photo fits gets the product's primary photo, else its first.
    None when there are no photos.

    `media_items` is the product's photos (pass a prefetched list, with
    `attribute_values` prefetched, to avoid extra queries); the variant's
    `attribute_values` should be prefetched too.
    """
    items = sorted(media_items, key=lambda m: (m.sort_order, str(m.pk)))
    if not items:
        return None
    value_ids = {av.pk for av in variant.attribute_values.all()} if variant is not None else set()
    pool = items
    if value_ids:
        fitting = []
        for m in items:
            tags = media_tag_ids(m)
            if tags and tags <= value_ids:
                fitting.append((len(tags), m))
        if fitting:
            best = max(n for n, _ in fitting)
            pool = [m for n, m in fitting if n == best]
    return next((m for m in pool if m.is_primary), pool[0])


def photo_for_variant(variant):
    """
    `variant_photo` for one variant, loading the product's photos if they
    weren't prefetched. For one-off lookups (cart line, order snapshot, email).
    """
    if variant is None or getattr(variant, "product", None) is None:
        return None
    product = variant.product
    if "media" in getattr(product, "_prefetched_objects_cache", {}):
        items = list(product.media.all())
    else:
        items = list(product.media.prefetch_related("attribute_values"))
    return variant_photo(variant, items)
