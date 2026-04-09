"""
catalog.selectors
~~~~~~~~~~~~~~~~~
Read-only query helpers for the catalog.

Every function is cache-ready: the caller can wrap any selector
with Django's cache framework (django.core.cache.cache.get/set)
or decorate with a caching layer later without changing business logic.

Pattern:
    # Cache-ready usage in views:
    from django.core.cache import cache

    def get_product(product_id):
        key = f"product:{product_id}"
        result = cache.get(key)
        if result is None:
            result = selectors.get_product_by_id(product_id)
            cache.set(key, result, timeout=300)
        return result
"""

from __future__ import annotations

from django.db.models import QuerySet, Prefetch, Q, Min, Max, Count
from .models import (
    Category, Brand, Product, ProductMedia,
    Attribute, AttributeValue, ProductVariant,
    GlobalAttribute, GlobalAttributeOption, ProductAttributeConfig, ProductInfoItem,
)


# ─────────────────────────────────────────────────────────────
#  Category
# ─────────────────────────────────────────────────────────────

def get_all_categories(*, active_only: bool = True, latest_first: bool = False) -> QuerySet:
    qs = Category.all_objects if not active_only else Category.objects
    qs = qs.select_related("parent").prefetch_related("children")
    if latest_first:
        qs = qs.order_by("-created_at")
    return qs


def get_category_by_id(category_id) -> Category | None:
    try:
        return Category.all_objects.select_related("parent").get(id=category_id)
    except Category.DoesNotExist:
        return None


def get_category_by_slug(slug: str) -> Category | None:
    try:
        return Category.all_objects.select_related("parent").get(slug=slug)
    except Category.DoesNotExist:
        return None


# ─────────────────────────────────────────────────────────────
#  Brand
# ─────────────────────────────────────────────────────────────

def get_all_brands(*, active_only: bool = True) -> QuerySet:
    qs = Brand.objects.all()
    if active_only:
        qs = qs.filter(is_active=True)
    return qs


def get_brand_by_id(brand_id) -> Brand | None:
    try:
        return Brand.objects.get(id=brand_id)
    except Brand.DoesNotExist:
        return None


# ─────────────────────────────────────────────────────────────
#  Product
# ─────────────────────────────────────────────────────────────

def get_product_by_id(product_id, *, published_only: bool = False) -> Product | None:
    manager = Product.published if published_only else Product.all_objects
    try:
        return (
            manager
            .select_related("category", "brand")
            .prefetch_related(
                Prefetch("media", queryset=ProductMedia.objects.order_by("sort_order")),
                Prefetch("variants", queryset=ProductVariant.objects.filter(is_active=True).prefetch_related("attribute_values__attribute")),
                Prefetch("info_items", queryset=ProductInfoItem.objects.order_by("sort_order", "created_at")),
                "attributes__values",
                "global_attribute_configs__global_attribute__options",
            )
            .get(id=product_id)
        )
    except Product.DoesNotExist:
        return None


def get_product_by_slug(slug: str, *, published_only: bool = True) -> Product | None:
    manager = Product.published if published_only else Product.all_objects
    try:
        return (
            manager
            .select_related("category", "brand")
            .prefetch_related(
                Prefetch("media", queryset=ProductMedia.objects.order_by("sort_order")),
                Prefetch("variants", queryset=ProductVariant.objects.filter(is_active=True).prefetch_related("attribute_values__attribute")),
                Prefetch("info_items", queryset=ProductInfoItem.objects.order_by("sort_order", "created_at")),
                "attributes__values",
                "global_attribute_configs__global_attribute__options",
            )
            .get(slug=slug)
        )
    except Product.DoesNotExist:
        return None


def get_product_list(
    *,
    category_id=None,
    brand_id=None,
    is_featured: bool | None = None,
    is_active: bool = True,
    search: str | None = None,
    price_min=None,
    price_max=None,
    attribute_value_ids: list | None = None,
    published_only: bool = True,
    include_deleted: bool = False,
) -> QuerySet:
    """
    Composable product list query used by ListProductView and filters.
    All parameters are optional — combine as needed.
    """
    manager = Product.published if published_only else Product.all_objects
    qs = manager.select_related("category", "brand").annotate(
        image_count=Count("media", distinct=True),
    ).prefetch_related(
        Prefetch("media", queryset=ProductMedia.objects.filter(is_primary=True)),
        "variants",
    )

    # Admin/staff queries may use all_objects for visibility of inactive products,
    # but catalog lists should hide soft-deleted items unless explicitly requested.
    if not include_deleted:
        qs = qs.filter(deleted_at__isnull=True)

    if category_id:
        # Include children categories
        child_ids = list(
            Category.all_objects.filter(parent_id=category_id).values_list("id", flat=True)
        )
        qs = qs.filter(category_id__in=[category_id, *child_ids])

    if brand_id:
        qs = qs.filter(brand_id=brand_id)

    if is_featured is not None:
        qs = qs.filter(is_featured=is_featured)

    if search:
        qs = qs.filter(
            Q(name__icontains=search) |
            Q(description__icontains=search) |
            Q(variants__sku__icontains=search)
        ).distinct()

    if price_min is not None:
        qs = qs.filter(variants__price__gte=price_min)

    if price_max is not None:
        qs = qs.filter(variants__price__lte=price_max)

    if attribute_value_ids:
        for av_id in attribute_value_ids:
            qs = qs.filter(variants__attribute_values__id=av_id)
        qs = qs.distinct()

    return qs.order_by("-is_featured", "-created_at")


def get_deal_products(*, limit: int = 10) -> QuerySet:
    """
    Returns products that have at least one variant with an active offer.
    Ordered by the maximum discount percentage among their active offer variants.
    """
    from django.utils import timezone
    from django.db.models import Max, F, ExpressionWrapper, DecimalField

    now = timezone.now()

    # Filter variants with live offers
    active_variants = ProductVariant.objects.filter(
        is_active=True,
        offer_is_active=True,
        offer_price__isnull=False,
        price__gt=F('offer_price')
    ).filter(
        Q(offer_starts_at__isnull=True) | Q(offer_starts_at__lte=now)
    ).filter(
        Q(offer_ends_at__isnull=True) | Q(offer_ends_at__gte=now)
    )

    # Annotated version to get max discount percentage
    # Discount % = ((price - offer_price) / price) * 100
    qs = Product.published.filter(
        variants__id__in=active_variants.values_list('id', flat=True)
    ).annotate(
        max_discount=Max(
            ExpressionWrapper(
                (F('variants__price') - F('variants__offer_price')) * 100.0 / F('variants__price'),
                output_field=DecimalField()
            ),
            filter=Q(variants__id__in=active_variants)
        )
    ).select_related("category", "brand").prefetch_related(
        Prefetch("media", queryset=ProductMedia.objects.all().order_by("sort_order")),
        Prefetch("variants", queryset=active_variants)
    )

    return qs.order_by("-max_discount")[:limit]


# ─────────────────────────────────────────────────────────────
#  Variant
# ─────────────────────────────────────────────────────────────

def get_variant_by_id(variant_id) -> ProductVariant | None:
    try:
        return (
            ProductVariant.objects
            .select_related("product")
            .prefetch_related("attribute_values__attribute")
            .get(id=variant_id)
        )
    except ProductVariant.DoesNotExist:
        return None


def get_variant_by_sku(sku: str) -> ProductVariant | None:
    try:
        return ProductVariant.objects.select_related("product").get(sku=sku)
    except ProductVariant.DoesNotExist:
        return None


def get_variants_for_product(product: Product) -> QuerySet:
    return (
        ProductVariant.objects
        .filter(product=product)
        .prefetch_related("attribute_values__attribute")
        .order_by("is_default", "sku")
    )


def sku_exists(sku: str, exclude_id=None) -> bool:
    qs = ProductVariant.objects.filter(sku=sku)
    if exclude_id:
        qs = qs.exclude(id=exclude_id)
    return qs.exists()


# ─────────────────────────────────────────────────────────────
#  Attributes
# ─────────────────────────────────────────────────────────────

def get_attributes_for_product(product: Product) -> QuerySet:
    return (
        Attribute.objects
        .filter(product=product)
        .prefetch_related("values")
        .order_by("sort_order")
    )


def get_info_items_for_product(product: Product, *, active_only: bool = False) -> QuerySet:
    qs = ProductInfoItem.objects.filter(product=product)
    if active_only:
        qs = qs.filter(is_active=True)
    return qs.order_by("sort_order", "created_at")


def get_all_attributes(*, product_id=None, search: str | None = None) -> QuerySet:
    qs = Attribute.objects.select_related("product").prefetch_related("values")
    if product_id:
        qs = qs.filter(product_id=product_id)
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(product__name__icontains=search))
    return qs.order_by("product__name", "sort_order", "name")


def get_attribute_by_id(attribute_id) -> Attribute | None:
    try:
        return Attribute.objects.select_related("product").get(id=attribute_id)
    except Attribute.DoesNotExist:
        return None


def get_attribute_value_by_id(av_id) -> AttributeValue | None:
    try:
        return AttributeValue.objects.select_related("attribute__product").get(id=av_id)
    except AttributeValue.DoesNotExist:
        return None


def get_all_global_attributes(*, search: str | None = None, active_only: bool = False) -> QuerySet:
    qs = GlobalAttribute.objects.prefetch_related("options", "product_configs")
    if active_only:
        qs = qs.filter(is_active=True)
    if search:
        qs = qs.filter(name__icontains=search)
    return qs.order_by("sort_order", "name")


def get_global_attribute_by_id(attribute_id) -> GlobalAttribute | None:
    try:
        return GlobalAttribute.objects.prefetch_related("options", "product_configs").get(id=attribute_id)
    except GlobalAttribute.DoesNotExist:
        return None


def get_global_attribute_option_by_id(option_id) -> GlobalAttributeOption | None:
    try:
        return GlobalAttributeOption.objects.select_related("global_attribute").get(id=option_id)
    except GlobalAttributeOption.DoesNotExist:
        return None


def get_global_attributes_for_product(product: Product) -> QuerySet:
    return (
        ProductAttributeConfig.objects
        .filter(product=product, is_active=True, global_attribute__is_active=True)
        .select_related("global_attribute")
        .prefetch_related("global_attribute__options")
        .order_by("sort_order", "global_attribute__name")
    )


def get_product_attribute_config(product: Product, global_attribute: GlobalAttribute) -> ProductAttributeConfig | None:
    try:
        return ProductAttributeConfig.objects.get(product=product, global_attribute=global_attribute)
    except ProductAttributeConfig.DoesNotExist:
        return None
