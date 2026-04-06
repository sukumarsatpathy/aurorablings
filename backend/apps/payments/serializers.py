from rest_framework import serializers
from .models import PaymentTransaction, WebhookLog, Refund
from .providers.registry import registry


class PaymentTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model  = PaymentTransaction
        fields = [
            "id", "order", "provider", "provider_ref",
            "razorpay_order_id", "razorpay_payment_id",
            "status", "total_amount", "refunded_amount", "amount", "currency",
            "payment_url", "client_secret",
            "retry_count", "max_retries", "can_retry",
            "created_at", "updated_at",
        ]
        read_only_fields = fields
    can_retry = serializers.BooleanField(read_only=True)


class InitiatePaymentSerializer(serializers.Serializer):
    order_id     = serializers.UUIDField()
    provider     = serializers.CharField()
    currency     = serializers.CharField(required=False, default="INR")
    return_url   = serializers.URLField(required=False, default="")

    def validate_provider(self, value):
        if not registry.is_registered(value):
            raise serializers.ValidationError(
                f"Unknown provider '{value}'. Available: {registry.names()}"
            )
        return value


class RetryPaymentSerializer(serializers.Serializer):
    transaction_id = serializers.UUIDField()
    return_url     = serializers.URLField(required=False, default="")


class ReconcilePaymentSerializer(serializers.Serializer):
    order_id = serializers.UUIDField()


class RazorpayCreateOrderSerializer(serializers.Serializer):
    order_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency = serializers.CharField(required=False, default="INR")


class RazorpayCreateOrderResponseSerializer(serializers.Serializer):
    transaction_id = serializers.UUIDField()
    razorpay_order_id = serializers.CharField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency = serializers.CharField()
    key_id = serializers.CharField()


class RazorpayVerifyPaymentSerializer(serializers.Serializer):
    razorpay_order_id = serializers.CharField()
    razorpay_payment_id = serializers.CharField()
    razorpay_signature = serializers.CharField()


class RefundSerializer(serializers.Serializer):
    transaction_id = serializers.UUIDField()
    amount         = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)
    reason         = serializers.CharField(required=False, default="")


class RefundCreateSerializer(serializers.Serializer):
    order_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    reason = serializers.CharField(required=False, default="")


class RefundRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = Refund
        fields = [
            "id",
            "order",
            "payment",
            "refund_id",
            "cf_refund_id",
            "amount",
            "status",
            "source",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class WebhookLogSerializer(serializers.ModelSerializer):
    class Meta:
        model  = WebhookLog
        fields = [
            "id", "provider", "provider_ref", "order_ref",
            "event_status", "is_verified", "is_processed",
            "processing_error", "transaction",
            "created_at",
        ]
        read_only_fields = fields


class ProviderListSerializer(serializers.Serializer):
    """Serializes available payment providers for the frontend."""
    name                 = serializers.CharField()
    display_name         = serializers.CharField()
    supported_currencies = serializers.ListField(child=serializers.CharField())
    supports_refunds     = serializers.BooleanField()
    supports_webhooks    = serializers.BooleanField()
