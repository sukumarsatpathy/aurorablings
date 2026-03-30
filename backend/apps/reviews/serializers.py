from __future__ import annotations

from rest_framework import serializers

from core.media import validate_image_file

from .cache import SORT_OPTIONS
from .models import ProductReview, ReviewMedia, ReviewStatus, ReviewVoteType

MAX_REVIEW_IMAGES = 5


class ReviewMediaSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = ReviewMedia
        fields = ["id", "image", "sort_order", "created_at"]

    def get_image(self, obj):
        from core.media import build_media_url

        return build_media_url(obj.image, request=self.context.get("request"))


class PublicReviewSerializer(serializers.ModelSerializer):
    media = ReviewMediaSerializer(many=True, read_only=True)
    reviewer_name = serializers.SerializerMethodField()

    class Meta:
        model = ProductReview
        fields = [
            "id",
            "rating",
            "title",
            "comment",
            "is_verified_purchase",
            "is_featured",
            "helpful_count",
            "unhelpful_count",
            "created_at",
            "updated_at",
            "reviewer_name",
            "media",
        ]

    def get_reviewer_name(self, obj) -> str:
        full_name = f"{obj.user.first_name} {obj.user.last_name}".strip()
        if full_name:
            return full_name
        return obj.user.email.split("@")[0]


class MyReviewSerializer(serializers.ModelSerializer):
    media = ReviewMediaSerializer(many=True, read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = ProductReview
        fields = [
            "id",
            "product",
            "product_name",
            "rating",
            "title",
            "comment",
            "status",
            "is_verified_purchase",
            "is_featured",
            "is_edited",
            "helpful_count",
            "unhelpful_count",
            "created_at",
            "updated_at",
            "media",
        ]


class ReviewCreateUpdateSerializer(serializers.Serializer):
    rating = serializers.IntegerField(min_value=1, max_value=5)
    title = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    comment = serializers.CharField(max_length=2000)
    turnstile_token = serializers.CharField(required=False, allow_blank=True, write_only=True)
    images = serializers.ListField(
        child=serializers.ImageField(),
        required=False,
        allow_empty=True,
        default=list,
    )

    def validate_images(self, images):
        if len(images) > MAX_REVIEW_IMAGES:
            raise serializers.ValidationError(f"You can upload up to {MAX_REVIEW_IMAGES} images.")

        for image in images:
            try:
                validate_image_file(image)
            except Exception as exc:
                raise serializers.ValidationError(str(exc))
        return images


class ReviewVoteSerializer(serializers.Serializer):
    vote_type = serializers.ChoiceField(choices=ReviewVoteType.choices)


class ReviewSummarySerializer(serializers.Serializer):
    average_rating = serializers.FloatField()
    total_reviews = serializers.IntegerField()
    rating_breakdown = serializers.DictField(child=serializers.IntegerField())
    has_reviewed = serializers.BooleanField()
    my_review_id = serializers.UUIDField(allow_null=True)


class PublicReviewListQuerySerializer(serializers.Serializer):
    sort = serializers.ChoiceField(choices=[(item, item) for item in SORT_OPTIONS], default="featured_first")


class AdminReviewSerializer(serializers.ModelSerializer):
    media = ReviewMediaSerializer(many=True, read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    user_email = serializers.EmailField(source="user.email", read_only=True)
    moderated_by_email = serializers.EmailField(source="moderated_by.email", read_only=True, allow_null=True)

    class Meta:
        model = ProductReview
        fields = [
            "id",
            "product",
            "product_name",
            "user",
            "user_email",
            "rating",
            "title",
            "comment",
            "status",
            "is_verified_purchase",
            "is_featured",
            "is_edited",
            "is_soft_deleted",
            "helpful_count",
            "unhelpful_count",
            "moderated_at",
            "moderated_by",
            "moderated_by_email",
            "admin_notes",
            "created_at",
            "updated_at",
            "media",
        ]


class ReviewModerationSerializer(serializers.Serializer):
    admin_notes = serializers.CharField(required=False, allow_blank=True, default="")
    is_featured = serializers.BooleanField(required=False)


class AdminReviewFilterSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=ReviewStatus.choices, required=False)
    product = serializers.UUIDField(required=False)
    rating = serializers.IntegerField(min_value=1, max_value=5, required=False)
    verified_purchase = serializers.BooleanField(required=False)
    featured = serializers.BooleanField(required=False)
    search = serializers.CharField(required=False, allow_blank=True)
