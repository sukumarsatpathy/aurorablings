"""
catalog.filters
~~~~~~~~~~~~~~~
django-filter FilterSet classes for the catalog API.

Usage in view:
    filterset_class = ProductFilter
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
"""
import django_filters
from django.db.models import Q
from .models import Product, Category, Brand, AttributeValue


class ProductFilter(django_filters.FilterSet):
    """
    Supports:
      ?category=<id>           filter by category (includes children)
      ?brand=<id>
      ?is_featured=true
      ?price_min=100
      ?price_max=999
      ?search=ring             name / description / sku
      ?attributes=<av_id>,<av_id>   comma-separated attribute value IDs
      ?ordering=price,-created_at
    """
    category    = django_filters.UUIDFilter(method="filter_category")
    brand       = django_filters.UUIDFilter(field_name="brand__id")
    is_featured = django_filters.BooleanFilter()
    price_min   = django_filters.NumberFilter(method="filter_price_min")
    price_max   = django_filters.NumberFilter(method="filter_price_max")
    search      = django_filters.CharFilter(method="filter_search")
    attributes  = django_filters.CharFilter(method="filter_attributes")
    has_offer   = django_filters.BooleanFilter(method="filter_has_offer")
    ordering    = django_filters.OrderingFilter(
        fields=(
            ("created_at",    "created_at"),
            ("name",          "name"),
            ("variants__price", "price"),
            ("is_featured",   "featured"),
        )
    )

    class Meta:
        model  = Product
        fields = ["category", "brand", "is_featured", "has_offer"]

    def filter_has_offer(self, qs, name, value):
        from django.utils import timezone
        now = timezone.now()
        if value:
            # Active offer filter
            return qs.filter(
                variants__is_active=True,
                variants__offer_is_active=True,
                variants__offer_price__isnull=False,
            ).filter(
                Q(variants__offer_starts_at__isnull=True) | Q(variants__offer_starts_at__lte=now)
            ).filter(
                Q(variants__offer_ends_at__isnull=True) | Q(variants__offer_ends_at__gte=now)
            ).distinct()
        else:
            # No active offer filter
            # (Matches what get_deal_products excludes)
            active_variant_ids = Product.objects.filter(
                variants__is_active=True,
                variants__offer_is_active=True,
                variants__offer_price__isnull=False,
            ).filter(
                Q(variants__offer_starts_at__isnull=True) | Q(variants__offer_starts_at__lte=now)
            ).filter(
                Q(variants__offer_ends_at__isnull=True) | Q(variants__offer_ends_at__gte=now)
            ).values_list('id', flat=True)
            return qs.exclude(id__in=active_variant_ids)

    def filter_category(self, qs, name, value):
        child_ids = list(
            Category.all_objects.filter(parent_id=value).values_list("id", flat=True)
        )
        return qs.filter(category_id__in=[value, *child_ids])

    def filter_price_min(self, qs, name, value):
        return qs.filter(variants__price__gte=value).distinct()

    def filter_price_max(self, qs, name, value):
        return qs.filter(variants__price__lte=value).distinct()

    def filter_search(self, qs, name, value):
        return qs.filter(
            Q(name__icontains=value) |
            Q(description__icontains=value) |
            Q(variants__sku__icontains=value)
        ).distinct()

    def filter_attributes(self, qs, name, value):
        """Accept comma-separated UUIDs: ?attributes=<id1>,<id2>"""
        ids = [v.strip() for v in value.split(",") if v.strip()]
        for av_id in ids:
            qs = qs.filter(variants__attribute_values__id=av_id)
        return qs.distinct()
