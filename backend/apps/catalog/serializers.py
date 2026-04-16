from django.db.models import Sum
from rest_framework import serializers
from core.media import build_media_url, validate_image_file
from .models import (
    Category, Brand, Product, ProductMedia,
    Attribute, AttributeValue, ProductVariant,
    GlobalAttribute, GlobalAttributeOption, ProductAttributeConfig, ProductInfoItem, ProductStockNotifyRequest,
)


# ─────────────────────────────────────────────────────────────
#  Category
# ─────────────────────────────────────────────────────────────

class CategorySerializer(serializers.ModelSerializer):
    parent_name = serializers.SerializerMethodField()
    product_count = serializers.SerializerMethodField()
    is_coming_soon = serializers.SerializerMethodField()
    image = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model  = Category
        fields = ["id", "name", "slug", "parent", "parent_name", "image", "description", "is_active", "sort_order", "product_count", "is_coming_soon"]
        read_only_fields = ["id", "slug", "product_count", "is_coming_soon"]

    def get_parent_name(self, obj) -> str | None:
        return obj.parent.name if obj.parent else None

    def get_product_count(self, obj) -> int:
        return obj.products.count()

    def get_is_coming_soon(self, obj) -> bool:
        # "Coming Soon" should mean category has no live products yet.
        return not obj.products.exists()

    def validate_image(self, value):
        if value in (None, ""):
            return value
        try:
            return validate_image_file(value)
        except Exception as exc:
            raise serializers.ValidationError(str(exc))

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["image"] = build_media_url(instance.image, request=self.context.get("request"))
        return data


class CategoryTreeSerializer(CategorySerializer):
    """Recursive — only use for shallow trees (< 3 levels)."""
    children = serializers.SerializerMethodField()

    class Meta(CategorySerializer.Meta):
        fields = CategorySerializer.Meta.fields + ["children"]

    def get_children(self, obj):
        return CategoryTreeSerializer(obj.children.filter(is_active=True), many=True).data


# ─────────────────────────────────────────────────────────────
#  Brand
# ─────────────────────────────────────────────────────────────

class BrandSerializer(serializers.ModelSerializer):
    logo = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model  = Brand
        fields = ["id", "name", "slug", "logo", "website", "is_active"]
        read_only_fields = ["id", "slug"]

    def validate_logo(self, value):
        if value in (None, ""):
            return value
        try:
            return validate_image_file(value)
        except Exception as exc:
            raise serializers.ValidationError(str(exc))

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["logo"] = build_media_url(instance.logo, request=self.context.get("request"))
        return data


# ─────────────────────────────────────────────────────────────
#  Attribute & Values
# ─────────────────────────────────────────────────────────────

class AttributeValueSerializer(serializers.ModelSerializer):
    class Meta:
        model  = AttributeValue
        fields = ["id", "value", "sort_order"]
        read_only_fields = ["id"]


class AttributeSerializer(serializers.ModelSerializer):
    values = AttributeValueSerializer(many=True, read_only=True)

    class Meta:
        model  = Attribute
        fields = ["id", "name", "sort_order", "values"]
        read_only_fields = ["id"]


class ProductAttributeWriteSerializer(serializers.Serializer):
    global_attribute_id = serializers.UUIDField(required=False)
    name = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    options = serializers.ListField(
        child=serializers.CharField(max_length=100, allow_blank=False),
        required=False,
        default=list,
    )


class GlobalAttributeOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = GlobalAttributeOption
        fields = ["id", "value", "sort_order", "is_active"]
        read_only_fields = ["id"]


class AttributeAdminSerializer(serializers.ModelSerializer):
    options = serializers.SerializerMethodField()
    linked_products = serializers.SerializerMethodField()

    class Meta:
        model = GlobalAttribute
        fields = ["id", "name", "sort_order", "is_active", "linked_products", "options"]

    def get_options(self, obj):
        return [
            value.value
            for value in obj.options.filter(is_active=True).order_by("sort_order", "value")
        ]

    def get_linked_products(self, obj):
        return obj.product_configs.filter(is_active=True).count()


class AttributeAdminWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    options = serializers.ListField(
        child=serializers.CharField(max_length=100, allow_blank=False),
        required=False,
        default=list,
    )
    sort_order = serializers.IntegerField(required=False, default=0)
    is_active = serializers.BooleanField(required=False, default=True)


# ─────────────────────────────────────────────────────────────
#  Media
# ─────────────────────────────────────────────────────────────

class ProductMediaSerializer(serializers.ModelSerializer):
    image = serializers.ImageField()
    image_small = serializers.ImageField(required=False, allow_null=True)
    image_medium = serializers.ImageField(required=False, allow_null=True)
    image_large = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model  = ProductMedia
        fields = [
            "id",
            "image",
            "image_small",
            "image_medium",
            "image_large",
            "alt_text",
            "is_primary",
            "sort_order",
        ]
        read_only_fields = ["id"]

    def validate_image(self, value):
        try:
            return validate_image_file(value)
        except Exception as exc:
            raise serializers.ValidationError(str(exc))

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        data["image"] = build_media_url(instance.image, request=request)
        data["image_small"] = build_media_url(instance.image_small, request=request) if instance.image_small else None
        data["image_medium"] = build_media_url(instance.image_medium, request=request) if instance.image_medium else None
        data["image_large"] = build_media_url(instance.image_large, request=request) if instance.image_large else None
        return data


class ProductInfoItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductInfoItem
        fields = ["id", "title", "value", "sort_order", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class ProductInfoItemWriteSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=120)
    value = serializers.CharField()
    sort_order = serializers.IntegerField(required=False, default=0)
    is_active = serializers.BooleanField(required=False, default=True)


class ProductInfoItemReorderRowSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    sort_order = serializers.IntegerField(min_value=0)


class ProductInfoItemReorderSerializer(serializers.Serializer):
    items = ProductInfoItemReorderRowSerializer(many=True)


class ProductStockNotifyRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductStockNotifyRequest
        fields = [
            "id",
            "product",
            "variant",
            "user",
            "name",
            "email",
            "phone",
            "quantity",
            "notes",
            "is_notified",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "product", "user", "is_notified", "created_at", "updated_at"]


class ProductStockNotifyRequestWriteSerializer(serializers.Serializer):
    variant_id = serializers.UUIDField(required=False, allow_null=True)
    name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    quantity = serializers.IntegerField(required=False, min_value=1, default=1)
    notes = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")

    def validate(self, attrs):
        attrs["name"] = (attrs.get("name") or "").strip()
        attrs["email"] = (attrs.get("email") or "").strip().lower()
        attrs["phone"] = (attrs.get("phone") or "").strip()
        attrs["notes"] = (attrs.get("notes") or "").strip()

        request = self.context.get("request")
        is_authenticated = bool(request and getattr(request, "user", None) and request.user.is_authenticated)
        if not is_authenticated and not attrs["email"] and not attrs["phone"]:
            raise serializers.ValidationError(
                {"email": ["Email or phone is required for guest notify requests."]}
            )
        return attrs


# ─────────────────────────────────────────────────────────────
#  Variant
# ─────────────────────────────────────────────────────────────

class AttributeValueSummarySerializer(serializers.ModelSerializer):
    attribute_name = serializers.CharField(source="attribute.name", read_only=True)

    class Meta:
        model  = AttributeValue
        fields = ["id", "attribute_name", "value"]


class ProductVariantSerializer(serializers.ModelSerializer):
    attribute_values   = AttributeValueSummarySerializer(many=True, read_only=True)
    discount_percentage = serializers.IntegerField(read_only=True)
    is_in_stock        = serializers.BooleanField(read_only=True)
    is_low_stock       = serializers.BooleanField(read_only=True)
    has_active_offer   = serializers.BooleanField(read_only=True)
    effective_price    = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    display_compare_at_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True, allow_null=True)

    class Meta:
        model  = ProductVariant
        fields = [
            "id", "sku", "name", "price", "compare_at_price",
            "offer_price", "offer_starts_at", "offer_ends_at", "offer_label", "offer_is_active",
            "has_active_offer", "effective_price", "display_compare_at_price",
            "stock_quantity", "allow_backorder", "is_active", "is_default",
            "attribute_values", "discount_percentage",
            "is_in_stock", "is_low_stock", "weight_grams",
        ]
        read_only_fields = ["id", "discount_percentage", "is_in_stock", "is_low_stock"]


class ProductVariantWriteSerializer(serializers.Serializer):
    """Used for create/update — accepts attribute_value_ids as a list."""
    sku                 = serializers.CharField(max_length=100)
    price               = serializers.DecimalField(max_digits=12, decimal_places=2)
    compare_at_price    = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)
    offer_price         = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)
    offer_starts_at     = serializers.DateTimeField(required=False, allow_null=True)
    offer_ends_at       = serializers.DateTimeField(required=False, allow_null=True)
    offer_label         = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")
    offer_is_active     = serializers.BooleanField(required=False, default=False)
    cost_price          = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)
    stock_quantity      = serializers.IntegerField(default=0)
    allow_backorder     = serializers.BooleanField(required=False, default=False)
    is_default          = serializers.BooleanField(default=False)
    attribute_value_ids = serializers.ListField(child=serializers.UUIDField(), default=list)
    weight_grams        = serializers.IntegerField(required=False, allow_null=True)
    name                = serializers.CharField(max_length=255, required=False, default="")

    def validate(self, attrs):
        price = attrs.get("price")
        offer_price = attrs.get("offer_price")
        starts = attrs.get("offer_starts_at")
        ends = attrs.get("offer_ends_at")

        if offer_price is not None and price is not None and offer_price >= price:
            raise serializers.ValidationError({"offer_price": "Offer price must be lower than regular price."})
        if starts and ends and ends <= starts:
            raise serializers.ValidationError({"offer_ends_at": "Offer end must be later than offer start."})
        if int(attrs.get("stock_quantity", 0)) < 0 and not bool(attrs.get("allow_backorder", False)):
            raise serializers.ValidationError({"stock_quantity": "Stock cannot be negative unless backorder is enabled."})
        return attrs


# ─────────────────────────────────────────────────────────────
#  Product — List (lightweight)
# ─────────────────────────────────────────────────────────────

class ProductListSerializer(serializers.ModelSerializer):
    primary_image  = serializers.SerializerMethodField()
    category_name  = serializers.CharField(source="category.name", read_only=True)
    brand_name     = serializers.CharField(source="brand.name", read_only=True, default=None)
    price_range    = serializers.SerializerMethodField()
    default_variant = serializers.SerializerMethodField()
    total_stock = serializers.SerializerMethodField()
    variant_count = serializers.SerializerMethodField()
    stock_summary = serializers.SerializerMethodField()
    image_count = serializers.IntegerField(read_only=True)
    hover_image = serializers.SerializerMethodField()

    has_active_offer = serializers.SerializerMethodField()

    class Meta:
        model  = Product
        fields = [
            "id", "name", "slug", "short_description",
            "category_name", "brand_name", "is_featured", "rating", "avg_rating", "review_count",
            "primary_image", "hover_image", "image_count", "price_range", "default_variant",
            "total_stock", "variant_count", "stock_summary",
            "has_active_offer", "is_active", "created_at",
        ]

    def get_has_active_offer(self, obj) -> bool:
        # Assumes obj.variants has been prefetched
        return any(v.is_offer_live() for v in obj.variants.all())

    def get_primary_image(self, obj) -> str | None:
        primary = next((m for m in obj.media.all() if m.is_primary), None)
        return build_media_url(primary.image, request=self.context.get("request")) if primary else None

    def get_hover_image(self, obj) -> str | None:
        """Returns the second image in the media list as the hover image."""
        media = list(obj.media.all())
        if len(media) > 1:
            return build_media_url(media[1].image, request=self.context.get("request"))
        return None

    def get_price_range(self, obj) -> dict:
        return obj.price_range

    def get_default_variant(self, obj) -> dict | None:
        # Use prefetched variants if available
        variants = list(obj.variants.all())
        if not variants:
            return None
        # Prefer explicit default, otherwise pick first active variant
        variant = next((v for v in variants if v.is_default and v.is_active), None)
        if not variant:
            variant = next((v for v in variants if v.is_active), variants[0])
            
        return {
            "id": str(variant.id),
            "sku": variant.sku,
            "price": str(variant.price),
            "compare_at_price": str(variant.compare_at_price) if variant.compare_at_price is not None else None,
            "offer_price": str(variant.offer_price) if variant.offer_price is not None else None,
            "offer_starts_at": variant.offer_starts_at.isoformat() if variant.offer_starts_at else None,
            "offer_ends_at": variant.offer_ends_at.isoformat() if variant.offer_ends_at else None,
            "offer_label": variant.offer_label or "",
            "offer_is_active": bool(variant.offer_is_active),
            "has_active_offer": bool(variant.is_offer_live()),
            "effective_price": str(variant.effective_price),
            "display_compare_at_price": (
                str(variant.display_compare_at_price) if variant.display_compare_at_price is not None else None
            ),
            "discount_percentage": variant.discount_percentage,
            "stock_quantity": int(variant.stock_quantity or 0),
        }

    def _active_variants(self, obj):
        return [v for v in obj.variants.all() if v.is_active]

    def get_total_stock(self, obj) -> int:
        from django.db.models import Sum
        try:
            from apps.inventory.models import WarehouseStock
            stock_qs = WarehouseStock.objects.filter(variant__product=obj, variant__is_active=True)
            if stock_qs.exists():
                return int(stock_qs.aggregate(total=Sum("available"))["total"] or 0)
            raise Exception("No warehouse records")
        except Exception:
            return sum(int(v.stock_quantity or 0) for v in self._active_variants(obj))

    def get_variant_count(self, obj) -> int:
        return len(self._active_variants(obj))

    def get_stock_summary(self, obj) -> str:
        try:
            from apps.inventory.models import WarehouseStock
            from django.db.models import Sum
            variant_rows = (
                WarehouseStock.objects
                .filter(variant__product=obj, warehouse__is_active=True)
                .values("variant__sku")
                .annotate(total_available=Sum("available"))
                .order_by("variant__sku")
            )
            rows = list(variant_rows)
            if not rows:
                return ""
            preview = rows[:3]
            parts = [f"{r['variant__sku']}: {int(r['total_available'] or 0)}" for r in preview]
            if len(rows) > len(preview):
                parts.append(f"+{len(rows) - len(preview)} more")
            return " | ".join(parts)
        except Exception:
            variants = self._active_variants(obj)
            if not variants:
                return ""
            preview = variants[:3]
            parts = [f"{v.sku}: {int(v.stock_quantity or 0)}" for v in preview]
            if len(variants) > len(preview):
                parts.append(f"+{len(variants) - len(preview)} more")
            return " | ".join(parts)


# ─────────────────────────────────────────────────────────────
#  Deal Product (includes variant offer data for countdown timer)
# ─────────────────────────────────────────────────────────────

class DealProductSerializer(ProductListSerializer):
    """Extended serializer for deal products that includes variant offer data."""
    variants = ProductVariantSerializer(many=True, read_only=True)

    class Meta(ProductListSerializer.Meta):
        fields = ProductListSerializer.Meta.fields + ["variants"]


# ─────────────────────────────────────────────────────────────
#  Product — Detail (full)
# ─────────────────────────────────────────────────────────────

class ProductDetailSerializer(serializers.ModelSerializer):
    category   = CategorySerializer(read_only=True)
    brand      = BrandSerializer(read_only=True)
    media      = ProductMediaSerializer(many=True, read_only=True)
    variants   = ProductVariantSerializer(many=True, read_only=True)
    attributes = AttributeSerializer(many=True, read_only=True)
    info_items = serializers.SerializerMethodField()
    price_range = serializers.SerializerMethodField()

    class Meta:
        model  = Product
        fields = [
            "id", "name", "slug", "description", "short_description",
            "category", "brand", "is_active", "is_featured", "is_digital", "rating", "avg_rating", "review_count",
            "media", "variants", "attributes", "info_items", "price_range",
            "meta_title", "meta_description", "created_at", "updated_at",
        ]

    def get_price_range(self, obj) -> dict:
        return obj.price_range

    def get_info_items(self, obj):
        qs = obj.info_items.filter(is_active=True).order_by("sort_order", "created_at")
        return ProductInfoItemSerializer(qs, many=True).data


# ─────────────────────────────────────────────────────────────
#  Product — Write
# ─────────────────────────────────────────────────────────────

class ProductWriteSerializer(serializers.Serializer):
    name              = serializers.CharField(max_length=255)
    category_id       = serializers.UUIDField()
    brand_id          = serializers.UUIDField(required=False, allow_null=True)
    description       = serializers.CharField(required=False, allow_blank=True, default="")
    short_description = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    is_active         = serializers.BooleanField(default=True)
    is_featured       = serializers.BooleanField(default=False)
    is_digital        = serializers.BooleanField(default=False)
    rating            = serializers.DecimalField(max_digits=3, decimal_places=2, required=False, default=0.0)
    meta_title        = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    meta_description  = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
