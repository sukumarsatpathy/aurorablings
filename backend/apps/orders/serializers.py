from rest_framework import serializers
from .models import Order, OrderItem, OrderStatusHistory, PaymentMethod, OrderStatus, PaymentStatus
from core.media import build_media_url


class OrderStatusHistorySerializer(serializers.ModelSerializer):
    changed_by_email = serializers.SerializerMethodField()

    class Meta:
        model  = OrderStatusHistory
        fields = ["id", "from_status", "to_status", "changed_by_email", "notes", "created_at"]
        read_only_fields = fields

    def get_changed_by_email(self, obj) -> str | None:
        return obj.changed_by.email if obj.changed_by else None


class OrderItemSerializer(serializers.ModelSerializer):
    product_image = serializers.SerializerMethodField()
    product_id = serializers.SerializerMethodField()
    can_review = serializers.SerializerMethodField()
    has_reviewed = serializers.SerializerMethodField()
    my_review_id = serializers.SerializerMethodField()
    review_eligibility_reason = serializers.SerializerMethodField()

    class Meta:
        model  = OrderItem
        fields = [
            "id", "sku", "product_name", "variant_name",
            "quantity", "unit_price", "compare_at_price", "line_total",
            "product_snapshot", "product_image", "product_id",
            "can_review", "has_reviewed", "my_review_id", "review_eligibility_reason",
        ]
        read_only_fields = fields

    def get_product_image(self, obj) -> str | None:
        request = self.context.get("request")
        snapshot = obj.product_snapshot or {}
        snapshot_image = str(snapshot.get("image_url", "") or "").strip()
        if snapshot_image:
            return build_media_url(snapshot_image, request=request)

        variant = getattr(obj, "variant", None)
        if variant and getattr(variant, "product", None):
            media = variant.product.media.filter(is_primary=True).first() or variant.product.media.first()
            if media and getattr(media, "image", None):
                return build_media_url(media.image, request=request)
        return None

    def _resolve_product_id(self, obj) -> str | None:
        snapshot = obj.product_snapshot or {}
        from_snapshot = str(snapshot.get("product_id") or "").strip()
        if from_snapshot:
            return from_snapshot
        variant = getattr(obj, "variant", None)
        product_id = getattr(variant, "product_id", None) if variant else None
        return str(product_id) if product_id else None

    def _review_meta(self, obj) -> dict[str, object]:
        item_key = str(obj.id)
        cache = getattr(self, "_review_meta_cache", {})
        if item_key in cache:
            return cache[item_key]

        request = self.context.get("request")
        user = getattr(request, "user", None)
        product_id = self._resolve_product_id(obj)

        meta = {
            "product_id": product_id,
            "can_review": False,
            "has_reviewed": False,
            "my_review_id": None,
            "review_eligibility_reason": "Login to review this product.",
        }

        if not product_id:
            meta["review_eligibility_reason"] = "Review unavailable for this item."
        elif not user or not getattr(user, "is_authenticated", False):
            meta["review_eligibility_reason"] = "Login to review this product."
        else:
            from apps.reviews.models import ProductReview

            existing_review_id = (
                ProductReview.objects
                .filter(product_id=product_id, user_id=user.id, is_soft_deleted=False)
                .values_list("id", flat=True)
                .first()
            )
            if existing_review_id:
                meta["has_reviewed"] = True
                meta["my_review_id"] = str(existing_review_id)
                meta["review_eligibility_reason"] = "You have already submitted a review for this product."
            elif obj.order.status not in {OrderStatus.DELIVERED, OrderStatus.COMPLETED}:
                meta["review_eligibility_reason"] = "Reviews are available after a delivered purchase."
            else:
                meta["can_review"] = True
                meta["review_eligibility_reason"] = ""

        cache[item_key] = meta
        self._review_meta_cache = cache
        return meta

    def get_product_id(self, obj) -> str | None:
        return self._review_meta(obj)["product_id"]  # type: ignore[index]

    def get_can_review(self, obj) -> bool:
        return bool(self._review_meta(obj)["can_review"])

    def get_has_reviewed(self, obj) -> bool:
        return bool(self._review_meta(obj)["has_reviewed"])

    def get_my_review_id(self, obj) -> str | None:
        value = self._review_meta(obj)["my_review_id"]
        return str(value) if value else None

    def get_review_eligibility_reason(self, obj) -> str:
        return str(self._review_meta(obj)["review_eligibility_reason"] or "")


class OrderListSerializer(serializers.ModelSerializer):
    """Lightweight — used in list / my-orders views."""
    item_count = serializers.IntegerField(read_only=True)
    customer_name = serializers.SerializerMethodField()
    customer_email = serializers.SerializerMethodField()
    invoice_url = serializers.SerializerMethodField()

    class Meta:
        model  = Order
        fields = [
            "id", "order_number", "status", "payment_status",
            "grand_total", "currency", "item_count", "customer_name", "customer_email",
            "placed_at", "created_at", "invoice_url",
        ]
        read_only_fields = fields

    def get_customer_name(self, obj) -> str:
        if obj.user:
            full_name = obj.user.get_full_name().strip()
            if full_name:
                return full_name
        shipping_name = (obj.shipping_address or {}).get("full_name")
        if shipping_name:
            return str(shipping_name)
        return "Guest"

    def get_customer_email(self, obj) -> str:
        if obj.user and obj.user.email:
            return obj.user.email
        return obj.guest_email or ""

    def get_invoice_url(self, obj) -> str:
        from apps.invoices.services.invoice_service import InvoiceService

        return InvoiceService.build_invoice_url(order_id=str(obj.id))


class OrderDetailSerializer(serializers.ModelSerializer):
    """Full order detail including items and history."""
    items          = OrderItemSerializer(many=True, read_only=True)
    status_history = OrderStatusHistorySerializer(many=True, read_only=True)
    item_count     = serializers.IntegerField(read_only=True)
    customer_name  = serializers.SerializerMethodField()
    customer_email = serializers.SerializerMethodField()
    shipment = serializers.SerializerMethodField()
    invoice_url = serializers.SerializerMethodField()

    class Meta:
        model  = Order
        fields = [
            "id", "order_number",
            "status", "payment_status", "payment_method", "payment_reference",
            "customer_name", "customer_email", "guest_email",
            "shipping_address", "billing_address",
            "subtotal", "coupon_code", "discount_amount", "shipping_cost", "tax_amount",
            "grand_total", "currency",
            "tracking_number", "shipping_carrier",
            "shipment",
            "invoice_url",
            "notes",
            "item_count", "items", "status_history",
            "placed_at", "paid_at", "shipped_at", "delivered_at",
            "cancelled_at", "created_at", "updated_at",
        ]
        read_only_fields = fields

    def get_customer_name(self, obj) -> str:
        if obj.user:
            full_name = obj.user.get_full_name().strip()
            if full_name:
                return full_name
        shipping_name = (obj.shipping_address or {}).get("full_name")
        if shipping_name:
            return str(shipping_name)
        return "Guest"

    def get_customer_email(self, obj) -> str:
        if obj.user and obj.user.email:
            return obj.user.email
        return obj.guest_email or ""

    def get_shipment(self, obj):
        from apps.invoices.services.invoice_service import InvoiceService

        shipment = getattr(obj, "shipment", None)
        if not shipment:
            return None
        return {
            "id": str(shipment.id),
            "provider": shipment.provider,
            "status": shipment.status,
            "awb_code": shipment.awb_code,
            "courier_name": shipment.courier_name,
            "tracking_url": shipment.tracking_url,
            "label_url": shipment.label_url,
            "manifest_url": shipment.manifest_url,
            "invoice_url": shipment.invoice_url or InvoiceService.build_invoice_url(order_id=str(obj.id)),
            "pickup_requested": shipment.pickup_requested,
            "error_code": shipment.error_code,
            "error_message": shipment.error_message,
            "events": [
                {
                    "id": str(event.id),
                    "source": event.source,
                    "provider_status": event.provider_status,
                    "internal_status": event.internal_status,
                    "event_payload": event.event_payload,
                    "created_at": event.created_at,
                }
                for event in shipment.events.all().order_by("-created_at")
            ],
        }

    def get_invoice_url(self, obj) -> str:
        from apps.invoices.services.invoice_service import InvoiceService

        return InvoiceService.build_invoice_url(order_id=str(obj.id))


# ── Write serializers ─────────────────────────────────────────

class PlaceOrderSerializer(serializers.Serializer):
    shipping_address = serializers.DictField(child=serializers.CharField())
    billing_address  = serializers.DictField(child=serializers.CharField(), required=False)
    payment_method   = serializers.ChoiceField(
        choices=PaymentMethod.choices, default=PaymentMethod.COD
    )
    shipping_cost    = serializers.DecimalField(max_digits=10, decimal_places=2, default="0")
    coupon_code      = serializers.CharField(required=False, allow_blank=True, default="")
    notes            = serializers.CharField(required=False, allow_blank=True, default="")
    warehouse_id     = serializers.UUIDField(required=False, allow_null=True)
    guest_email      = serializers.EmailField(required=False, default="")
    # For guest carts
    session_key      = serializers.CharField(required=False, default="")
    create_account   = serializers.BooleanField(required=False, default=False)
    account          = serializers.DictField(required=False, default=dict)
    save_address     = serializers.BooleanField(required=False, default=True)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        account = attrs.get("account") or {}
        create_account = bool(attrs.get("create_account"))
        if create_account:
            required_fields = ["email", "password", "first_name", "last_name"]
            missing = [field for field in required_fields if not str(account.get(field, "") or "").strip()]
            if missing:
                raise serializers.ValidationError(
                    {"account": [f"Missing required account field(s): {', '.join(missing)}"]}
                )
        return attrs


class TransitionSerializer(serializers.Serializer):
    new_status = serializers.ChoiceField(choices=OrderStatus.choices)
    notes      = serializers.CharField(required=False, allow_blank=True, default="")


class MarkPaidSerializer(serializers.Serializer):
    payment_reference = serializers.CharField(required=False, default="")
    payment_method    = serializers.ChoiceField(choices=PaymentMethod.choices, required=False)


class MarkShippedSerializer(serializers.Serializer):
    tracking_number  = serializers.CharField(required=False, default="")
    shipping_carrier = serializers.CharField(required=False, default="")


class CancelOrderSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, default="Order cancelled.")


class AdminOrderItemInputSerializer(serializers.Serializer):
    variant_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1)


class AdminOrderCreateSerializer(serializers.Serializer):
    user_id = serializers.UUIDField(required=False, allow_null=True)
    guest_email = serializers.EmailField(required=False, allow_blank=True, default="")
    status = serializers.ChoiceField(choices=OrderStatus.choices, default=OrderStatus.PLACED)
    payment_status = serializers.ChoiceField(choices=PaymentStatus.choices, required=False, default=PaymentStatus.PENDING)
    payment_method = serializers.ChoiceField(choices=PaymentMethod.choices, required=False, default=PaymentMethod.COD)
    shipping_address = serializers.DictField(
        child=serializers.CharField(allow_blank=True, allow_null=True, required=False),
        required=False,
        default=dict,
    )
    billing_address = serializers.DictField(
        child=serializers.CharField(allow_blank=True, allow_null=True, required=False),
        required=False,
        default=dict,
    )
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default="0")
    discount_amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default="0")
    shipping_cost = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default="0")
    tax_amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default="0")
    grand_total = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default="0")
    currency = serializers.CharField(required=False, default="INR")
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    internal_notes = serializers.CharField(required=False, allow_blank=True, default="")
    coupon_code = serializers.CharField(required=False, allow_blank=True, default="")
    warehouse_id = serializers.UUIDField(required=False, allow_null=True)
    items = AdminOrderItemInputSerializer(many=True, required=False, default=list)


class AdminOrderUpdateSerializer(serializers.Serializer):
    payment_status = serializers.ChoiceField(choices=PaymentStatus.choices, required=False)
    payment_method = serializers.ChoiceField(choices=PaymentMethod.choices, required=False)
    shipping_address = serializers.DictField(
        child=serializers.CharField(allow_blank=True, allow_null=True, required=False),
        required=False,
    )
    billing_address = serializers.DictField(
        child=serializers.CharField(allow_blank=True, allow_null=True, required=False),
        required=False,
    )
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    discount_amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    shipping_cost = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    tax_amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    grand_total = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    currency = serializers.CharField(required=False)
    notes = serializers.CharField(required=False, allow_blank=True)
    internal_notes = serializers.CharField(required=False, allow_blank=True)
    tracking_number = serializers.CharField(required=False, allow_blank=True)
    shipping_carrier = serializers.CharField(required=False, allow_blank=True)


class AdminOrderCalculateSerializer(serializers.Serializer):
    user_id = serializers.UUIDField(required=False, allow_null=True)
    payment_method = serializers.ChoiceField(choices=PaymentMethod.choices, required=False, default=PaymentMethod.COD)
    shipping_address = serializers.DictField(
        child=serializers.CharField(allow_blank=True, allow_null=True, required=False),
        required=False,
        default=dict,
    )
    coupon_code = serializers.CharField(required=False, allow_blank=True, default="")
    items = AdminOrderItemInputSerializer(many=True, required=True)
