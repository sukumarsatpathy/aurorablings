from __future__ import annotations

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from core.models import BaseModel


class ReviewStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    HIDDEN = "hidden", "Hidden"


class ReviewVoteType(models.TextChoices):
    HELPFUL = "helpful", "Helpful"
    UNHELPFUL = "unhelpful", "Unhelpful"


class ProductReview(BaseModel):
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="product_reviews",
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    title = models.CharField(max_length=255, blank=True)
    comment = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=ReviewStatus.choices,
        default=ReviewStatus.PENDING,
        db_index=True,
    )

    is_verified_purchase = models.BooleanField(default=False, db_index=True)
    is_featured = models.BooleanField(default=False, db_index=True)
    is_edited = models.BooleanField(default=False)
    is_soft_deleted = models.BooleanField(default=False, db_index=True)

    helpful_count = models.PositiveIntegerField(default=0)
    unhelpful_count = models.PositiveIntegerField(default=0)

    moderated_at = models.DateTimeField(null=True, blank=True, db_index=True)
    moderated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="moderated_product_reviews",
    )
    admin_notes = models.TextField(blank=True)

    submitted_ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["product", "status", "created_at"]),
            models.Index(fields=["product", "status", "is_soft_deleted"]),
            models.Index(fields=["product", "is_featured", "created_at"]),
            models.Index(fields=["user", "product"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=Q(rating__gte=1) & Q(rating__lte=5),
                name="reviews_rating_between_1_and_5",
            ),
            models.UniqueConstraint(
                fields=["product", "user"],
                condition=Q(is_soft_deleted=False),
                name="reviews_unique_active_review_per_user_product",
            ),
        ]

    def __str__(self) -> str:
        return f"Review {self.id} for {self.product_id}"


class ReviewMedia(BaseModel):
    review = models.ForeignKey(
        ProductReview,
        on_delete=models.CASCADE,
        related_name="media",
    )
    image = models.ImageField(upload_to="reviews/%Y/%m/")
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "created_at"]
        indexes = [models.Index(fields=["review", "sort_order"])]

    def __str__(self) -> str:
        return f"ReviewMedia {self.id}"


class ReviewVote(BaseModel):
    review = models.ForeignKey(
        ProductReview,
        on_delete=models.CASCADE,
        related_name="votes",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="review_votes",
    )
    vote_type = models.CharField(max_length=20, choices=ReviewVoteType.choices)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["review", "user"],
                name="reviews_unique_vote_per_user_per_review",
            ),
        ]
        indexes = [
            models.Index(fields=["review", "vote_type"]),
            models.Index(fields=["user", "review"]),
        ]

    def __str__(self) -> str:
        return f"Vote {self.vote_type} by {self.user_id}"
