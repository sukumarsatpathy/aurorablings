from rest_framework import serializers
from .models import Order, OrderItem, OrderStatusHistory, PaymentMethod, OrderStatus


class OrderStatusHistorySerializer(serializers.ModelSerializer):
    changed_by_email = serializers.SerializerMethodField()

    class Meta:
        model  = OrderStatusHistory
        fields = ["id", "from_status", "to_status", "changed_by_email", "notes", "created_at"]
        read_only_fields = fields

    def get_changed_by_email(self, obj) -> str | None:
        return obj.changed_by.email if obj.changed_by else None


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model  = OrderItem
        fields = [
            "id", "sku", "product_name", "variant_name",
            "quantity", "unit_price", "compare_at_price", "line_total",
            "product_snapshot",
        ]
        read_only_fields = fields


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
    payment_status = serializers.CharField(required=False, default="pending")
    payment_method = serializers.ChoiceField(choices=PaymentMethod.choices, required=False, default=PaymentMethod.COD)
    shipping_address = serializers.DictField(child=serializers.CharField(), required=False, default=dict)
    billing_address = serializers.DictField(child=serializers.CharField(), required=False, default=dict)
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
    payment_status = serializers.CharField(required=False)
    payment_method = serializers.ChoiceField(choices=PaymentMethod.choices, required=False)
    shipping_address = serializers.DictField(child=serializers.CharField(), required=False)
    billing_address = serializers.DictField(child=serializers.CharField(), required=False)
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
    shipping_address = serializers.DictField(child=serializers.CharField(), required=False, default=dict)
    coupon_code = serializers.CharField(required=False, allow_blank=True, default="")
    items = AdminOrderItemInputSerializer(many=True, required=True)
