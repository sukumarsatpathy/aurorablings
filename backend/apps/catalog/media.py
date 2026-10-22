"""Picking the right photo for a variant."""

from __future__ import annotations


def variant_photo(variant, media_items):
    """
    The photo that shows this variant.

    Photos can be tagged with an option (Products → image → "Colour"). A
    variant whose options include a tagged one gets that photo — the primary
    of those if several, else the first by sort order. Otherwise the
    product's primary photo, else its first. None when there are no photos.

    `media_items` is the product's photos (pass a prefetched list to avoid
    extra queries); the variant's `attribute_values` should be prefetched too.
    """
    items = sorted(media_items, key=lambda m: (m.sort_order, str(m.pk)))
    if not items:
        return None
    value_ids = {av.pk for av in variant.attribute_values.all()} if variant is not None else set()
    tagged = [m for m in items if m.attribute_value_id and m.attribute_value_id in value_ids]
    pool = tagged or items
    return next((m for m in pool if m.is_primary), pool[0])
