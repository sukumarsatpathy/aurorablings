from __future__ import annotations

from django.core.cache import cache
from django.db import transaction
from django.db.models import Avg, Count, Q
from django.utils import timezone

from audit.models import ActorType, AuditAction
from audit.services.activity_logger import log_activity
from core.exceptions import ConflictError, NotFoundError, PermissionDeniedError
from core.logging import get_logger
from core.media import validate_image_file

from apps.catalog.models import Product
from apps.orders.models import OrderStatus
from apps.orders.models import OrderItem, PaymentStatus

from .cache import public_review_summary_key
from .models import ProductReview, ReviewMedia, ReviewStatus, ReviewVote, ReviewVoteType

logger = get_logger(__name__)


def _invalidate_review_cache(*, product_id) -> None:
    cache.delete(public_review_summary_key(str(product_id)))
    try:
        cache.delete_pattern(f"reviews:list:{product_id}:*")
    except Exception:
        for sort_key in ("newest", "highest_rating", "lowest_rating", "most_helpful", "featured_first"):
            for page in range(1, 4):
                for page_size in (20, 50, 100):
                    cache.delete(f"reviews:list:{product_id}:{sort_key}:p{page}:s{page_size}")


def _is_verified_purchase(*, user_id, product_id) -> bool:
    return OrderItem.objects.filter(
        order__user_id=user_id,
        variant__product_id=product_id,
    ).exclude(
        order__status__in=[OrderStatus.DRAFT, OrderStatus.CANCELLED],
    ).filter(
        Q(order__status__in=[
            OrderStatus.PAID,
            OrderStatus.PROCESSING,
            OrderStatus.SHIPPED,
            OrderStatus.DELIVERED,
            OrderStatus.COMPLETED,
            OrderStatus.PARTIALLY_REFUNDED,
            OrderStatus.REFUNDED,
        ]) | Q(order__payment_status__in=[
            PaymentStatus.PAID,
            PaymentStatus.PARTIALLY_REFUNDED,
            PaymentStatus.REFUNDED,
        ])
    ).exists()


def get_review_eligibility(*, user, product_id) -> tuple[bool, str]:
    existing = ProductReview.objects.filter(
        product_id=product_id,
        user=user,
        is_soft_deleted=False,
    ).first()
    if existing:
        return False, "You have already submitted a review for this product."

    has_purchase = _is_verified_purchase(user_id=user.id, product_id=product_id)
    if not has_purchase:
        return False, "Reviews are available after a confirmed purchase."
    return True, ""


def _run_abuse_checks(*, title: str, comment: str) -> None:
    # TODO: Plug in profanity filter provider once moderation service is selected.
    # TODO: Plug in spam scoring model before auto-approval workflows are introduced.
    _ = (title, comment)


@transaction.atomic
def submit_review(
    *,
    product_id,
    user,
    rating: int,
    title: str,
    comment: str,
    images: list,
    submitted_ip: str | None,
    user_agent: str,
    request=None,
) -> ProductReview:
    product = Product.published.filter(id=product_id).first()
    if not product:
        raise NotFoundError("Product not found.")

    existing = ProductReview.objects.filter(
        product_id=product_id,
        user=user,
        is_soft_deleted=False,
    ).first()
    if existing:
        raise ConflictError("You have already submitted a review for this product.")

    can_review, reason = get_review_eligibility(user=user, product_id=product.id)
    if not can_review:
        raise PermissionDeniedError(reason)

    _run_abuse_checks(title=title, comment=comment)

    review = ProductReview.objects.create(
        product=product,
        user=user,
        rating=rating,
        title=title.strip(),
        comment=comment.strip(),
        status=ReviewStatus.PENDING,
        is_verified_purchase=_is_verified_purchase(user_id=user.id, product_id=product.id),
        submitted_ip=submitted_ip,
        user_agent=(user_agent or "")[:512],
    )

    for idx, image in enumerate(images or []):
        image = validate_image_file(image)
        ReviewMedia.objects.create(review=review, image=image, sort_order=idx)

    recalculate_product_review_stats(product_id=product.id)
    _invalidate_review_cache(product_id=product.id)

    log_activity(
        user=user,
        actor_type=ActorType.CUSTOMER,
        action=AuditAction.CREATE,
        entity_type="product_review",
        entity_id=str(review.id),
        description=f"Submitted review for product '{product.name}'",
        metadata={"product_id": str(product.id), "rating": review.rating, "status": review.status},
        request=request,
    )

    logger.info("review_submitted", review_id=str(review.id), product_id=str(product.id), user_id=str(user.id))
    return review


@transaction.atomic
def update_review(
    *,
    review: ProductReview,
    user,
    rating: int,
    title: str,
    comment: str,
    images: list,
    request=None,
) -> ProductReview:
    if review.user_id != user.id:
        raise PermissionDeniedError("You can edit only your own review.")
    if review.is_soft_deleted:
        raise NotFoundError("Review not found.")

    _run_abuse_checks(title=title, comment=comment)

    review.rating = rating
    review.title = title.strip()
    review.comment = comment.strip()
    review.status = ReviewStatus.PENDING
    review.is_edited = True
    review.is_featured = False
    review.moderated_at = None
    review.moderated_by = None
    review.admin_notes = ""
    review.save(
        update_fields=[
            "rating",
            "title",
            "comment",
            "status",
            "is_edited",
            "is_featured",
            "moderated_at",
            "moderated_by",
            "admin_notes",
            "updated_at",
        ]
    )

    if images is not None:
        review.media.all().delete()
        for idx, image in enumerate(images):
            image = validate_image_file(image)
            ReviewMedia.objects.create(review=review, image=image, sort_order=idx)

    recalculate_product_review_stats(product_id=review.product_id)
    _invalidate_review_cache(product_id=review.product_id)

    log_activity(
        user=user,
        actor_type=ActorType.CUSTOMER,
        action=AuditAction.UPDATE,
        entity_type="product_review",
        entity_id=str(review.id),
        description="Updated own review and moved back to moderation queue",
        metadata={"product_id": str(review.product_id), "status": review.status},
        request=request,
    )

    return review


@transaction.atomic
def delete_review(*, review: ProductReview, user, request=None) -> None:
    if review.user_id != user.id:
        raise PermissionDeniedError("You can delete only your own review.")
    if review.is_soft_deleted:
        return

    review.is_soft_deleted = True
    review.is_featured = False
    review.status = ReviewStatus.HIDDEN
    review.save(update_fields=["is_soft_deleted", "is_featured", "status", "updated_at"])

    recalculate_product_review_stats(product_id=review.product_id)
    _invalidate_review_cache(product_id=review.product_id)

    log_activity(
        user=user,
        actor_type=ActorType.CUSTOMER,
        action=AuditAction.DELETE,
        entity_type="product_review",
        entity_id=str(review.id),
        description="Soft deleted own review",
        metadata={"product_id": str(review.product_id)},
        request=request,
    )


@transaction.atomic
def moderate_review(
    *,
    review: ProductReview,
    moderator,
    action: str,
    admin_notes: str = "",
    is_featured: bool | None = None,
    request=None,
) -> ProductReview:
    if action not in {"approve", "reject", "hide", "feature"}:
        raise ConflictError("Invalid moderation action.")

    if action == "approve":
        review.status = ReviewStatus.APPROVED
    elif action == "reject":
        review.status = ReviewStatus.REJECTED
        review.is_featured = False
    elif action == "hide":
        review.status = ReviewStatus.HIDDEN
        review.is_featured = False
    elif action == "feature":
        if review.status != ReviewStatus.APPROVED:
            raise ConflictError("Only approved reviews can be featured.")
        review.is_featured = True if is_featured is None else bool(is_featured)

    if action in {"approve", "reject", "hide"} and is_featured is not None:
        review.is_featured = bool(is_featured)

    review.moderated_at = timezone.now()
    review.moderated_by = moderator
    review.admin_notes = admin_notes.strip()
    review.save(
        update_fields=[
            "status",
            "is_featured",
            "moderated_at",
            "moderated_by",
            "admin_notes",
            "updated_at",
        ]
    )

    recalculate_product_review_stats(product_id=review.product_id)
    _invalidate_review_cache(product_id=review.product_id)

    log_activity(
        user=moderator,
        actor_type=ActorType.ADMIN if moderator.role == "admin" else ActorType.STAFF,
        action=AuditAction.STATUS_CHANGE,
        entity_type="product_review",
        entity_id=str(review.id),
        description=f"Moderation action '{action}' applied to review",
        metadata={
            "product_id": str(review.product_id),
            "status": review.status,
            "is_featured": review.is_featured,
            "admin_notes": review.admin_notes,
        },
        request=request,
    )

    if action == "approve":
        # TODO: Grant reward points/coins after approval.
        # TODO: Trigger post-approval acknowledgement notification.
        pass

    return review


@transaction.atomic
def recalculate_product_review_stats(*, product_id) -> None:
    product = Product.all_objects.filter(id=product_id).first()
    if not product:
        return

    aggregates = ProductReview.objects.filter(
        product_id=product_id,
        status=ReviewStatus.APPROVED,
        is_soft_deleted=False,
    ).aggregate(avg_rating=Avg("rating"), review_count=Count("id"))

    avg_rating = round(float(aggregates["avg_rating"] or 0.0), 2)
    review_count = int(aggregates["review_count"] or 0)

    product.avg_rating = avg_rating
    product.review_count = review_count
    product.rating = avg_rating
    product.save(update_fields=["avg_rating", "review_count", "rating", "updated_at"])


@transaction.atomic
def cast_review_vote(*, review: ProductReview, user, vote_type: str, request=None) -> ProductReview:
    if review.is_soft_deleted or review.status != ReviewStatus.APPROVED:
        raise NotFoundError("Review not found.")
    if review.user_id == user.id:
        raise ConflictError("You cannot vote on your own review.")

    vote, created = ReviewVote.objects.get_or_create(
        review=review,
        user=user,
        defaults={"vote_type": vote_type},
    )
    if not created and vote.vote_type != vote_type:
        vote.vote_type = vote_type
        vote.save(update_fields=["vote_type", "updated_at"])

    counts = (
        ReviewVote.objects
        .filter(review=review)
        .values("vote_type")
        .annotate(total=Count("id"))
    )
    helpful = 0
    unhelpful = 0
    for row in counts:
        if row["vote_type"] == ReviewVoteType.HELPFUL:
            helpful = int(row["total"])
        if row["vote_type"] == ReviewVoteType.UNHELPFUL:
            unhelpful = int(row["total"])

    review.helpful_count = helpful
    review.unhelpful_count = unhelpful
    review.save(update_fields=["helpful_count", "unhelpful_count", "updated_at"])

    _invalidate_review_cache(product_id=review.product_id)

    log_activity(
        user=user,
        actor_type=ActorType.CUSTOMER,
        action=AuditAction.UPDATE,
        entity_type="review_vote",
        entity_id=str(review.id),
        description="Cast/updated review vote",
        metadata={"vote_type": vote_type, "review_id": str(review.id)},
        request=request,
    )

    return review
