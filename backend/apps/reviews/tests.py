from decimal import Decimal

from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import User
from apps.catalog.models import Category, Product, ProductVariant
from apps.orders.models import Order, OrderItem, OrderStatus
from apps.reviews.models import ProductReview, ReviewStatus, ReviewVote, ReviewVoteType
from apps.reviews.services import moderate_review, recalculate_product_review_stats


@override_settings(TURNSTILE_ENABLED=False, TURNSTILE_SITE_KEY="", TURNSTILE_SECRET_KEY="")
class ReviewApiTests(APITestCase):
    def setUp(self):
        self.client = APIClient()

        self.customer = User.objects.create_user(
            email="customer@example.com",
            password="password123",
            role="customer",
            first_name="John",
            last_name="Doe",
        )
        self.customer_two = User.objects.create_user(
            email="customer2@example.com",
            password="password123",
            role="customer",
            first_name="Jane",
            last_name="Doe",
        )
        self.staff = User.objects.create_user(
            email="staff@example.com",
            password="password123",
            role="staff",
            is_staff=True,
        )

        self.category = Category.objects.create(name="Necklaces", slug="necklaces")
        self.product = Product.objects.create(
            name="Aurora Necklace",
            slug="aurora-necklace",
            category=self.category,
            is_active=True,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            sku="NECK-001",
            price=Decimal("100.00"),
            stock_quantity=10,
            is_active=True,
            is_default=True,
        )

        self.product_reviews_url = f"/api/v1/reviews/products/{self.product.id}/reviews/"
        self.product_summary_url = f"/api/v1/reviews/products/{self.product.id}/review-summary/"

    def test_public_sees_only_approved_reviews(self):
        ProductReview.objects.create(
            product=self.product,
            user=self.customer,
            rating=5,
            title="Great",
            comment="Loved it",
            status=ReviewStatus.APPROVED,
        )
        ProductReview.objects.create(
            product=self.product,
            user=self.customer_two,
            rating=4,
            title="Pending",
            comment="Awaiting",
            status=ReviewStatus.PENDING,
        )

        response = self.client.get(self.product_reviews_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["data"]), 1)
        self.assertEqual(response.data["data"][0]["comment"], "Loved it")

    def test_logged_in_user_can_create_review(self):
        self.client.force_authenticate(user=self.customer)

        payload = {"rating": 5, "title": "Excellent", "comment": "Very good quality"}
        response = self.client.post(self.product_reviews_url, payload, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        review = ProductReview.objects.get(user=self.customer, product=self.product, is_soft_deleted=False)
        self.assertEqual(review.status, ReviewStatus.PENDING)

    def test_anonymous_user_cannot_create_review(self):
        payload = {"rating": 5, "title": "Excellent", "comment": "Very good quality"}
        response = self.client.post(self.product_reviews_url, payload, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_one_review_per_user_per_product_enforced(self):
        ProductReview.objects.create(
            product=self.product,
            user=self.customer,
            rating=4,
            title="First",
            comment="First review",
            status=ReviewStatus.PENDING,
        )
        self.client.force_authenticate(user=self.customer)

        payload = {"rating": 5, "title": "Second", "comment": "Second review"}
        response = self.client.post(self.product_reviews_url, payload, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_edit_review_resets_status_to_pending(self):
        review = ProductReview.objects.create(
            product=self.product,
            user=self.customer,
            rating=4,
            title="Old",
            comment="Old comment",
            status=ReviewStatus.APPROVED,
        )
        self.client.force_authenticate(user=self.customer)

        response = self.client.patch(
            f"/api/v1/reviews/reviews/{review.id}/",
            {"rating": 3, "title": "Updated", "comment": "Updated comment"},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        review.refresh_from_db()
        self.assertEqual(review.status, ReviewStatus.PENDING)
        self.assertTrue(review.is_edited)

    def test_approved_reviews_update_product_aggregates(self):
        review = ProductReview.objects.create(
            product=self.product,
            user=self.customer,
            rating=5,
            title="Nice",
            comment="Nice product",
            status=ReviewStatus.PENDING,
        )

        moderate_review(review=review, moderator=self.staff, action="approve")
        self.product.refresh_from_db()

        self.assertEqual(float(self.product.avg_rating), 5.0)
        self.assertEqual(self.product.review_count, 1)

    def test_rejected_or_hidden_reviews_do_not_affect_aggregates(self):
        ProductReview.objects.create(
            product=self.product,
            user=self.customer,
            rating=5,
            title="A",
            comment="A",
            status=ReviewStatus.APPROVED,
        )
        ProductReview.objects.create(
            product=self.product,
            user=self.customer_two,
            rating=1,
            title="B",
            comment="B",
            status=ReviewStatus.REJECTED,
        )
        third_user = User.objects.create_user(email="c3@example.com", password="password123", role="customer")
        ProductReview.objects.create(
            product=self.product,
            user=third_user,
            rating=1,
            title="C",
            comment="C",
            status=ReviewStatus.HIDDEN,
        )

        recalculate_product_review_stats(product_id=self.product.id)
        self.product.refresh_from_db()

        self.assertEqual(float(self.product.avg_rating), 5.0)
        self.assertEqual(self.product.review_count, 1)

    def test_verified_purchase_flag_works(self):
        order = Order.objects.create(
            user=self.customer,
            status=OrderStatus.DELIVERED,
            shipping_address={},
            billing_address={},
            subtotal=Decimal("100.00"),
            grand_total=Decimal("100.00"),
        )
        OrderItem.objects.create(
            order=order,
            variant=self.variant,
            sku=self.variant.sku,
            product_name=self.product.name,
            variant_name=self.variant.name,
            product_snapshot={},
            quantity=1,
            unit_price=Decimal("100.00"),
            line_total=Decimal("100.00"),
        )

        self.client.force_authenticate(user=self.customer)
        response = self.client.post(
            self.product_reviews_url,
            {"rating": 5, "title": "Verified", "comment": "Bought this"},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        review = ProductReview.objects.get(user=self.customer, product=self.product, is_soft_deleted=False)
        self.assertTrue(review.is_verified_purchase)

    def test_helpful_vote_uniqueness_per_user_per_review(self):
        review = ProductReview.objects.create(
            product=self.product,
            user=self.customer,
            rating=5,
            title="Great",
            comment="Great",
            status=ReviewStatus.APPROVED,
        )

        self.client.force_authenticate(user=self.customer_two)
        url = f"/api/v1/reviews/reviews/{review.id}/vote/"

        response1 = self.client.post(url, {"vote_type": ReviewVoteType.HELPFUL})
        response2 = self.client.post(url, {"vote_type": ReviewVoteType.UNHELPFUL})

        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertEqual(ReviewVote.objects.filter(review=review, user=self.customer_two).count(), 1)
        review.refresh_from_db()
        self.assertEqual(review.helpful_count, 0)
        self.assertEqual(review.unhelpful_count, 1)

    def test_admin_moderation_endpoint_permissions(self):
        review = ProductReview.objects.create(
            product=self.product,
            user=self.customer,
            rating=5,
            title="Pending",
            comment="Pending review",
            status=ReviewStatus.PENDING,
        )
        url = f"/api/v1/reviews/admin/reviews/{review.id}/approve/"

        self.client.force_authenticate(user=self.customer_two)
        forbidden = self.client.post(url, {"admin_notes": "No access"})
        self.assertEqual(forbidden.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.staff)
        allowed = self.client.post(url, {"admin_notes": "Approved"})
        self.assertEqual(allowed.status_code, status.HTTP_200_OK)
        review.refresh_from_db()
        self.assertEqual(review.status, ReviewStatus.APPROVED)
