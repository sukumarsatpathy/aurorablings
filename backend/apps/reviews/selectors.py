from __future__ import annotations

from django.db.models import Count, QuerySet
from django.db.models.functions import Coalesce

from apps.catalog.models import Product

from .cache import SORT_OPTIONS
from .models import ProductReview, ReviewStatus


def get_product_or_none(product_id, *, published_only: bool = True) -> Product | None:
    manager = Product.published if published_only else Product.all_objects
    try:
        return manager.get(id=product_id)
    except Product.DoesNotExist:
        return None


def get_review_by_id(review_id) -> ProductReview | None:
    try:
        return (
            ProductReview.objects
            .select_related("user", "product", "moderated_by")
            .prefetch_related("media")
            .get(id=review_id)
        )
    except ProductReview.DoesNotExist:
        return None


def get_public_reviews_queryset(*, product_id, sort_by: str = "featured_first") -> QuerySet:
    sort_value = sort_by if sort_by in SORT_OPTIONS else "featured_first"
    qs = (
        ProductReview.objects
        .filter(
            product_id=product_id,
            status=ReviewStatus.APPROVED,
            is_soft_deleted=False,
        )
        .select_related("user")
        .prefetch_related("media")
        .annotate(vote_total=Coalesce("helpful_count", 0) - Coalesce("unhelpful_count", 0))
    )

    if sort_value == "newest":
        return qs.order_by("-created_at")
    if sort_value == "highest_rating":
        return qs.order_by("-rating", "-created_at")
    if sort_value == "lowest_rating":
        return qs.order_by("rating", "-created_at")
    if sort_value == "most_helpful":
        return qs.order_by("-helpful_count", "-vote_total", "-created_at")
    return qs.order_by("-is_featured", "-created_at")


def get_review_breakdown(*, product_id) -> dict[str, int]:
    rows = (
        ProductReview.objects
        .filter(
            product_id=product_id,
            status=ReviewStatus.APPROVED,
            is_soft_deleted=False,
        )
        .values("rating")
        .annotate(total=Count("id"))
    )
    breakdown = {str(i): 0 for i in range(1, 6)}
    for row in rows:
        breakdown[str(row["rating"])] = int(row["total"])
    return breakdown


def get_user_active_review(*, user_id, product_id) -> ProductReview | None:
    return (
        ProductReview.objects
        .filter(user_id=user_id, product_id=product_id, is_soft_deleted=False)
        .select_related("product", "user")
        .prefetch_related("media")
        .first()
    )


def get_user_reviews_queryset(*, user_id) -> QuerySet:
    return (
        ProductReview.objects
        .filter(user_id=user_id, is_soft_deleted=False)
        .select_related("product")
        .prefetch_related("media")
        .order_by("-updated_at")
    )


def get_admin_reviews_queryset(
    *,
    status: str | None = None,
    product_id=None,
    rating=None,
    verified_purchase: bool | None = None,
    featured: bool | None = None,
    search: str | None = None,
) -> QuerySet:
    qs = (
        ProductReview.objects
        .select_related("product", "user", "moderated_by")
        .prefetch_related("media")
        .order_by("-created_at")
    )

    if status:
        qs = qs.filter(status=status)
    if product_id:
        qs = qs.filter(product_id=product_id)
    if rating is not None:
        qs = qs.filter(rating=rating)
    if verified_purchase is not None:
        qs = qs.filter(is_verified_purchase=verified_purchase)
    if featured is not None:
        qs = qs.filter(is_featured=featured)
    if search:
        from django.db.models import Q
        qs = qs.filter(
            Q(title__icontains=search)
            | Q(comment__icontains=search)
            | Q(product__name__icontains=search)
            | Q(user__email__icontains=search)
            | Q(user__first_name__icontains=search)
            | Q(user__last_name__icontains=search)
        )
    return qs
