from django.urls import path

from . import views

app_name = "reviews"

urlpatterns = [
    path("products/<uuid:product_id>/reviews/", views.ProductReviewListCreateView.as_view(), name="product-reviews"),
    path("products/<uuid:product_id>/review-summary/", views.ProductReviewSummaryView.as_view(), name="product-review-summary"),

    path("reviews/<uuid:review_id>/", views.ReviewDetailView.as_view(), name="review-detail"),
    path("reviews/<uuid:review_id>/vote/", views.ReviewVoteView.as_view(), name="review-vote"),
    path("me/reviews/", views.MyReviewListView.as_view(), name="my-reviews"),

    path("admin/reviews/", views.AdminReviewListView.as_view(), name="admin-reviews"),
    path("admin/reviews/<uuid:review_id>/approve/", views.AdminReviewApproveView.as_view(), name="admin-review-approve"),
    path("admin/reviews/<uuid:review_id>/reject/", views.AdminReviewRejectView.as_view(), name="admin-review-reject"),
    path("admin/reviews/<uuid:review_id>/hide/", views.AdminReviewHideView.as_view(), name="admin-review-hide"),
    path("admin/reviews/<uuid:review_id>/feature/", views.AdminReviewFeatureView.as_view(), name="admin-review-feature"),
]
