from rest_framework import serializers
from .models import (
    ReturnRequest, ReturnItem, ExchangeRequest, ExchangeItem,
    ReturnStatusHistory, ReturnStatus, ExchangeStatus,
    ReturnReason, ItemCondition, ReturnPolicy,
)


class ReturnStatusHistorySerializer(serializers.ModelSerializer):
    changed_by_email = serializers.SerializerMethodField()
    class Meta:
        model  = ReturnStatusHistory
        fields = ["id", "from_status", "to_status", "changed_by_email", "notes", "created_at"]
        read_only_fields = fields
    def get_changed_by_email(self, obj): return obj.changed_by.email if obj.changed_by else None


class ReturnItemSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ReturnItem
        fields = [
            "id", "order_item", "variant", "quantity",
            "reason_code", "reason_detail", "condition",
            "unit_price", "refund_amount", "stock_reintegrated",
        ]
        read_only_fields = ["id", "unit_price", "refund_amount", "stock_reintegrated"]


class ReturnRequestSerializer(serializers.ModelSerializer):
    items          = ReturnItemSerializer(many=True, read_only=True)
    status_history = ReturnStatusHistorySerializer(many=True, read_only=True)
    order_number   = serializers.SerializerMethodField()
    customer_name  = serializers.SerializerMethodField()
    customer_email = serializers.SerializerMethodField()
    class Meta:
        model  = ReturnRequest
        fields = [
            "id", "return_number", "order", "status",
            "order_number", "customer_name", "customer_email",
            "refund_amount", "restocking_fee_applied", "is_refund_ready",
            "pickup_address", "return_tracking_no", "return_carrier",
            "notes", "staff_notes", "rejection_reason",
            "approved_at", "items_received_at", "inspected_at",
            "refund_initiated_at", "completed_at",
            "items", "status_history",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "return_number", "refund_amount", "restocking_fee_applied",
            "is_refund_ready", "approved_at", "items_received_at",
            "inspected_at", "refund_initiated_at", "completed_at",
        ]

    def get_order_number(self, obj):
        return getattr(obj.order, "order_number", "")

    def get_customer_name(self, obj):
        if obj.user:
            name = obj.user.get_full_name().strip()
            if name:
                return name
        shipping = obj.order.shipping_address or {}
        return str(shipping.get("full_name") or "Guest")

    def get_customer_email(self, obj):
        if obj.user and obj.user.email:
            return obj.user.email
        return obj.order.guest_email or ""


class ExchangeItemSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ExchangeItem
        fields = [
            "id", "order_item", "original_variant", "replacement_variant",
            "quantity", "reason_code", "reason_detail", "condition",
            "price_difference", "stock_reintegrated",
        ]
        read_only_fields = ["id", "price_difference", "stock_reintegrated"]


class ExchangeRequestSerializer(serializers.ModelSerializer):
    items          = ExchangeItemSerializer(many=True, read_only=True)
    status_history = ReturnStatusHistorySerializer(many=True, read_only=True)
    order_number   = serializers.SerializerMethodField()
    customer_name  = serializers.SerializerMethodField()
    customer_email = serializers.SerializerMethodField()
    class Meta:
        model  = ExchangeRequest
        fields = [
            "id", "exchange_number", "order", "status",
            "order_number", "customer_name", "customer_email",
            "return_tracking_no", "return_carrier",
            "exchange_tracking_no", "exchange_carrier", "shipping_address",
            "notes", "staff_notes", "rejection_reason",
            "approved_at", "items_received_at", "inspected_at",
            "exchange_shipped_at", "completed_at",
            "items", "status_history",
            "created_at", "updated_at",
        ]
        read_only_fields = fields

    def get_order_number(self, obj):
        return getattr(obj.order, "order_number", "")

    def get_customer_name(self, obj):
        if obj.user:
            name = obj.user.get_full_name().strip()
            if name:
                return name
        shipping = obj.order.shipping_address or {}
        return str(shipping.get("full_name") or "Guest")

    def get_customer_email(self, obj):
        if obj.user and obj.user.email:
            return obj.user.email
        return obj.order.guest_email or ""


# ── Write serializers ──────────────────────────────────────────

class ReturnItemInputSerializer(serializers.Serializer):
    order_item_id = serializers.UUIDField()
    quantity      = serializers.IntegerField(min_value=1)
    reason_code   = serializers.ChoiceField(choices=ReturnReason.choices)
    reason_detail = serializers.CharField(required=False, default="")
    warehouse_id  = serializers.UUIDField(required=False, allow_null=True)


class CreateReturnSerializer(serializers.Serializer):
    order_id        = serializers.UUIDField()
    items           = ReturnItemInputSerializer(many=True)
    notes           = serializers.CharField(required=False, allow_blank=True, default="")
    pickup_address  = serializers.DictField(required=False, allow_null=True)


class ExchangeItemInputSerializer(serializers.Serializer):
    order_item_id           = serializers.UUIDField()
    replacement_variant_id  = serializers.UUIDField()
    quantity                = serializers.IntegerField(min_value=1)
    reason_code             = serializers.ChoiceField(choices=ReturnReason.choices)
    reason_detail           = serializers.CharField(required=False, default="")


class CreateExchangeSerializer(serializers.Serializer):
    order_id         = serializers.UUIDField()
    items            = ExchangeItemInputSerializer(many=True)
    notes            = serializers.CharField(required=False, allow_blank=True, default="")
    shipping_address = serializers.DictField(required=False, allow_null=True)


class AdminCreateReturnSerializer(CreateReturnSerializer):
    user_id = serializers.UUIDField(required=False, allow_null=True)


class AdminCreateExchangeSerializer(CreateExchangeSerializer):
    user_id = serializers.UUIDField(required=False, allow_null=True)


class UpdateReturnSerializer(serializers.Serializer):
    notes = serializers.CharField(required=False, allow_blank=True)
    staff_notes = serializers.CharField(required=False, allow_blank=True)
    pickup_address = serializers.DictField(required=False)
    return_tracking_no = serializers.CharField(required=False, allow_blank=True)
    return_carrier = serializers.CharField(required=False, allow_blank=True)


class UpdateExchangeSerializer(serializers.Serializer):
    notes = serializers.CharField(required=False, allow_blank=True)
    staff_notes = serializers.CharField(required=False, allow_blank=True)
    shipping_address = serializers.DictField(required=False)
    return_tracking_no = serializers.CharField(required=False, allow_blank=True)
    return_carrier = serializers.CharField(required=False, allow_blank=True)
    exchange_tracking_no = serializers.CharField(required=False, allow_blank=True)
    exchange_carrier = serializers.CharField(required=False, allow_blank=True)


class ItemConditionInputSerializer(serializers.Serializer):
    item_id   = serializers.UUIDField()
    condition = serializers.ChoiceField(choices=ItemCondition.choices)


class InspectItemsSerializer(serializers.Serializer):
    item_conditions = ItemConditionInputSerializer(many=True)
    staff_notes     = serializers.CharField(required=False, default="")


class MarkReceivedSerializer(serializers.Serializer):
    tracking_no = serializers.CharField(required=False, default="")
    carrier     = serializers.CharField(required=False, default="")


class RejectSerializer(serializers.Serializer):
    reason = serializers.CharField()


class ShipExchangeSerializer(serializers.Serializer):
    tracking_no = serializers.CharField(required=False, default="")
    carrier     = serializers.CharField(required=False, default="")


class ReturnPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model  = ReturnPolicy
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]
