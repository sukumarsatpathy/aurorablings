from __future__ import annotations

from django.core.cache import cache
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from apps.accounts.permissions import IsStaffOrAdmin
from core.exceptions import NotFoundError
from core.pagination import StandardResultsPagination
from core.response import success_response, error_response
from core.turnstile import verify_turnstile_token, get_client_ip

from .cache import (
    PUBLIC_REVIEW_LIST_TTL,
    PUBLIC_REVIEW_SUMMARY_TTL,
    public_review_list_key,
    public_review_summary_key,
)
from . import selectors, services
from .serializers import (
    FlatReviewCreateSerializer,
    AdminReviewFilterSerializer,
    AdminReviewSerializer,
    MyReviewSerializer,
    PublicReviewListQuerySerializer,
    PublicReviewSerializer,
    ReviewCreateUpdateSerializer,
    ReviewModerationSerializer,
    ReviewSummarySerializer,
    ReviewVoteSerializer,
)


class AuthenticatedOrIPRateThrottle(SimpleRateThrottle):
    scope = "review_write"
    rate = "20/hour"

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = str(request.user.pk)
        else:
            ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}


class ReviewVoteRateThrottle(SimpleRateThrottle):
    scope = "review_vote"
    rate = "60/hour"

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = str(request.user.pk)
        else:
            ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}
class ProductReviewListCreateView(APIView):
    throttle_scope = "review_submit"

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_throttles(self):
        throttles = super().get_throttles()
        if self.request.method == "POST":
            throttles.append(AuthenticatedOrIPRateThrottle())
        return throttles

    def get(self, request, product_id):
        product = selectors.get_product_or_none(product_id, published_only=True)
        if not product:
            raise NotFoundError("Product not found.")

        query_serializer = PublicReviewListQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        sort_by = query_serializer.validated_data["sort"]

        paginator = StandardResultsPagination()
        queryset = selectors.get_public_reviews_queryset(product_id=product.id, sort_by=sort_by)
        page = paginator.paginate_queryset(queryset, request, view=self)
        if page is None:
            data = PublicReviewSerializer(queryset, many=True, context={"request": request}).data
            return success_response(data=data)

        page_num = int(request.query_params.get("page") or 1)
        page_size = int(paginator.get_page_size(request) or paginator.page_size)

        if page_num == 1:
            key = public_review_list_key(product_id=str(product.id), sort_by=sort_by, page=page_num, page_size=page_size)
            cached_payload = cache.get(key)
            if cached_payload:
                return success_response(
                    data=cached_payload["data"],
                    meta=cached_payload["meta"],
                    message="Data retrieved successfully.",
                    request_id=getattr(request, "request_id", None),
                )

        payload = PublicReviewSerializer(page, many=True, context={"request": request}).data
        meta = paginator._build_meta()

        if page_num == 1:
            cache.set(
                public_review_list_key(product_id=str(product.id), sort_by=sort_by, page=page_num, page_size=page_size),
                {"data": payload, "meta": meta},
                timeout=PUBLIC_REVIEW_LIST_TTL,
            )

        return success_response(
            data=payload,
            meta=meta,
            message="Data retrieved successfully.",
            request_id=getattr(request, "request_id", None),
        )

    def post(self, request, product_id):
        serializer = ReviewCreateUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if not verify_turnstile_token(
            token=serializer.validated_data.get("turnstile_token", ""),
            remote_ip=get_client_ip(request),
            action="reviews.submit",
        ):
            return error_response(
                message="CAPTCHA verification failed.",
                error_code="turnstile_verification_failed",
                errors={"turnstile_token": ["Invalid or missing CAPTCHA token."]},
                status_code=status.HTTP_400_BAD_REQUEST,
                request_id=getattr(request, "request_id", None),
            )

        review = services.submit_review(
            product_id=product_id,
            user=request.user,
            rating=serializer.validated_data["rating"],
            title=serializer.validated_data.get("title", ""),
            comment=serializer.validated_data["comment"],
            images=serializer.validated_data.get("images", []),
            submitted_ip=request.META.get("REMOTE_ADDR"),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
            request=request,
        )
        return success_response(
            data=MyReviewSerializer(review, context={"request": request}).data,
            message="Thanks. Your review has been submitted for approval.",
            status_code=status.HTTP_201_CREATED,
            request_id=getattr(request, "request_id", None),
        )


class ProductReviewSummaryView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, product_id):
        product = selectors.get_product_or_none(product_id, published_only=True)
        if not product:
            raise NotFoundError("Product not found.")

        cache_key = public_review_summary_key(str(product.id))
        summary = cache.get(cache_key)
        if summary is None:
            summary = {
                "average_rating": float(product.avg_rating or 0),
                "total_reviews": int(product.review_count or 0),
                "rating_breakdown": selectors.get_review_breakdown(product_id=product.id),
            }
            cache.set(cache_key, summary, timeout=PUBLIC_REVIEW_SUMMARY_TTL)

        has_reviewed = False
        my_review_id = None
        can_review = False
        eligibility_reason = "Login to review this product."
        if request.user and request.user.is_authenticated:
            my_review = selectors.get_user_active_review(user_id=request.user.id, product_id=product.id)
            if my_review:
                has_reviewed = True
                my_review_id = my_review.id
            can_review, eligibility_reason = services.get_review_eligibility(user=request.user, product_id=product.id)

        payload = {
            **summary,
            "has_reviewed": has_reviewed,
            "my_review_id": my_review_id,
            "can_review": can_review,
            "eligibility_reason": eligibility_reason,
        }
        data = ReviewSummarySerializer(payload).data
        return success_response(data=data, request_id=getattr(request, "request_id", None))


class FlatReviewCreateView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [AuthenticatedOrIPRateThrottle]

    def post(self, request):
        serializer = FlatReviewCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if not verify_turnstile_token(
            token=serializer.validated_data.get("turnstile_token", ""),
            remote_ip=get_client_ip(request),
            action="reviews.submit",
        ):
            return error_response(
                message="CAPTCHA verification failed.",
                error_code="turnstile_verification_failed",
                errors={"turnstile_token": ["Invalid or missing CAPTCHA token."]},
                status_code=status.HTTP_400_BAD_REQUEST,
                request_id=getattr(request, "request_id", None),
            )

        review = services.submit_review(
            product_id=serializer.validated_data["product_id"],
            user=request.user,
            rating=serializer.validated_data["rating"],
            title=serializer.validated_data.get("title", ""),
            comment=serializer.validated_data["comment"],
            images=serializer.validated_data.get("images", []),
            submitted_ip=request.META.get("REMOTE_ADDR"),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
            request=request,
        )
        return success_response(
            data=MyReviewSerializer(review, context={"request": request}).data,
            message="Thanks. Your review has been submitted for approval.",
            status_code=status.HTTP_201_CREATED,
            request_id=getattr(request, "request_id", None),
        )


class ReviewDetailView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [AuthenticatedOrIPRateThrottle]

    def patch(self, request, review_id):
        review = selectors.get_review_by_id(review_id)
        if not review or review.is_soft_deleted:
            raise NotFoundError("Review not found.")

        serializer = ReviewCreateUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        review = services.update_review(
            review=review,
            user=request.user,
            rating=serializer.validated_data["rating"],
            title=serializer.validated_data.get("title", ""),
            comment=serializer.validated_data["comment"],
            images=serializer.validated_data.get("images", []),
            request=request,
        )
        return success_response(
            data=MyReviewSerializer(review, context={"request": request}).data,
            message="Review updated and sent for re-approval.",
            request_id=getattr(request, "request_id", None),
        )

    def delete(self, request, review_id):
        review = selectors.get_review_by_id(review_id)
        if not review or review.is_soft_deleted:
            raise NotFoundError("Review not found.")

        services.delete_review(review=review, user=request.user, request=request)
        return success_response(
            message="Review deleted.",
            request_id=getattr(request, "request_id", None),
        )


class ReviewVoteView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ReviewVoteRateThrottle]

    def post(self, request, review_id):
        review = selectors.get_review_by_id(review_id)
        if not review:
            raise NotFoundError("Review not found.")

        serializer = ReviewVoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        review = services.cast_review_vote(
            review=review,
            user=request.user,
            vote_type=serializer.validated_data["vote_type"],
            request=request,
        )

        return success_response(
            data={
                "review_id": str(review.id),
                "helpful_count": review.helpful_count,
                "unhelpful_count": review.unhelpful_count,
            },
            message="Vote recorded.",
            request_id=getattr(request, "request_id", None),
        )


class MyReviewListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = selectors.get_user_reviews_queryset(user_id=request.user.id)
        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        if page is None:
            data = MyReviewSerializer(queryset, many=True, context={"request": request}).data
            return success_response(data=data, request_id=getattr(request, "request_id", None))

        payload = MyReviewSerializer(page, many=True, context={"request": request}).data
        return success_response(
            data=payload,
            meta=paginator._build_meta(),
            message="Data retrieved successfully.",
            request_id=getattr(request, "request_id", None),
        )


class AdminReviewListView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def get(self, request):
        filter_serializer = AdminReviewFilterSerializer(data=request.query_params)
        filter_serializer.is_valid(raise_exception=True)
        data = filter_serializer.validated_data

        queryset = selectors.get_admin_reviews_queryset(
            status=data.get("status"),
            product_id=data.get("product"),
            rating=data.get("rating"),
            verified_purchase=data.get("verified_purchase"),
            featured=data.get("featured"),
            search=data.get("search", ""),
        )

        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        if page is None:
            payload = AdminReviewSerializer(queryset, many=True, context={"request": request}).data
            return success_response(data=payload, request_id=getattr(request, "request_id", None))

        payload = AdminReviewSerializer(page, many=True, context={"request": request}).data
        return success_response(
            data=payload,
            meta=paginator._build_meta(),
            message="Data retrieved successfully.",
            request_id=getattr(request, "request_id", None),
        )


class _AdminReviewActionBaseView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]
    moderation_action = ""

    def post(self, request, review_id):
        review = selectors.get_review_by_id(review_id)
        if not review:
            raise NotFoundError("Review not found.")

        serializer = ReviewModerationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        updated = services.moderate_review(
            review=review,
            moderator=request.user,
            action=self.moderation_action,
            admin_notes=serializer.validated_data.get("admin_notes", ""),
            is_featured=serializer.validated_data.get("is_featured"),
            request=request,
        )

        return success_response(
            data=AdminReviewSerializer(updated, context={"request": request}).data,
            message=f"Review {self.moderation_action}d successfully.",
            request_id=getattr(request, "request_id", None),
        )


class AdminReviewApproveView(_AdminReviewActionBaseView):
    moderation_action = "approve"


class AdminReviewRejectView(_AdminReviewActionBaseView):
    moderation_action = "reject"


class AdminReviewHideView(_AdminReviewActionBaseView):
    moderation_action = "hide"


class AdminReviewFeatureView(_AdminReviewActionBaseView):
    moderation_action = "feature"
