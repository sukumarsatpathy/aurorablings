from __future__ import annotations

from decimal import Decimal
import io
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image

from apps.cart.models import Cart, CartItem
from apps.cart.serializers import CartItemReadSerializer
from apps.catalog.models import Category, Product, ProductMedia, ProductVariant

User = get_user_model()


class CartSerializerMediaUrlTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="cart-user@example.com",
            password="password123",
            role="customer",
        )
        self.category = Category.all_objects.create(name="Rings", slug="rings", is_active=True)
        self.product = Product.all_objects.create(
            name="Aurora Ring",
            slug="aurora-ring",
            category=self.category,
            is_active=True,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            sku="RING-001",
            price=Decimal("999.00"),
            stock_quantity=5,
            is_active=True,
            is_default=True,
        )
        buffer = io.BytesIO()
        Image.new("RGB", (20, 20), color=(150, 120, 60)).save(buffer, format="JPEG")
        image = SimpleUploadedFile("cart-test.jpg", buffer.getvalue(), content_type="image/jpeg")
        self.media = ProductMedia.objects.create(
            product=self.product,
            image=image,
            is_primary=True,
            sort_order=0,
        )
        self.cart = Cart.objects.create(user=self.user, status="active")
        self.item = CartItem.objects.create(
            cart=self.cart,
            variant=self.variant,
            quantity=1,
            unit_price=Decimal("999.00"),
        )

    def test_cart_serializer_uses_shared_build_media_url_helper(self):
        with patch("apps.cart.serializers.build_media_url", return_value="https://cdn.example.com/img.jpg") as mock_build:
            payload = CartItemReadSerializer(self.item, context={"request": None}).data

        self.assertEqual(payload["thumbnail"], "https://cdn.example.com/img.jpg")
        mock_build.assert_called()
