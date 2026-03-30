from decimal import Decimal
from rest_framework import serializers
from core.media import build_media_url
from .models import Cart, CartItem


class CartItemReadSerializer(serializers.ModelSerializer):
    sku              = serializers.CharField(source="variant.sku", read_only=True)
    product_name     = serializers.CharField(source="variant.product.name", read_only=True)
    variant_name     = serializers.CharField(source="variant.name", read_only=True)
    line_total       = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    is_price_stale   = serializers.BooleanField(read_only=True)
    current_price    = serializers.SerializerMethodField()
    thumbnail        = serializers.SerializerMethodField()
    attribute_values = serializers.SerializerMethodField()

    class Meta:
        model  = CartItem
        fields = [
            "id", "variant", "sku", "product_name", "variant_name",
            "attribute_values",
            "quantity", "unit_price", "compare_at_price",
            "current_price", "line_total", "is_price_stale",
            "thumbnail", "created_at", "updated_at",
        ]
        read_only_fields = fields

    def get_thumbnail(self, obj) -> str | None:
        media_qs = obj.variant.product.media.all()
        primary  = next((m for m in media_qs if m.is_primary), None) or (media_qs[0] if media_qs else None)
        return build_media_url(primary.image, request=self.context.get("request")) if primary else None

    def get_current_price(self, obj):
        return obj.variant.effective_price

    def get_attribute_values(self, obj) -> list[dict]:
        return [
            {"attribute": av.attribute.name, "value": av.value}
            for av in obj.variant.attribute_values.all()
        ]


class CartReadSerializer(serializers.ModelSerializer):
    items        = CartItemReadSerializer(many=True, read_only=True)
    item_count   = serializers.IntegerField(read_only=True)
    subtotal     = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    is_guest     = serializers.BooleanField(read_only=True)
    is_expired   = serializers.BooleanField(read_only=True)

    class Meta:
        model  = Cart
        fields = [
            "id", "status", "is_guest", "is_expired",
            "item_count", "subtotal",
            "items", "expires_at", "created_at", "updated_at",
        ]
        read_only_fields = fields


# ── Write serializers ──────────────────────────────────────────

class AddItemSerializer(serializers.Serializer):
    variant_id   = serializers.UUIDField()
    quantity     = serializers.IntegerField(min_value=1, max_value=100)
    warehouse_id = serializers.UUIDField(required=False, allow_null=True)
    coupon_code  = serializers.CharField(required=False, allow_blank=True, default="")


class UpdateItemSerializer(serializers.Serializer):
    quantity     = serializers.IntegerField(min_value=1, max_value=100)
    warehouse_id = serializers.UUIDField(required=False, allow_null=True)
    coupon_code  = serializers.CharField(required=False, allow_blank=True, default="")


class MergeCartSerializer(serializers.Serializer):
    session_key = serializers.CharField(max_length=64)
