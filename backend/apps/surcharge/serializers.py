from rest_framework import serializers
from .models import TaxRule, ShippingRule, FeeRule


class TaxRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model  = TaxRule
        fields = [
            "id", "name", "description", "tax_type", "tax_code", "hsn_code",
            "rate", "is_inclusive", "applies_to", "categories",
            "conditions", "priority", "is_active", "start_date", "end_date",
        ]
        read_only_fields = ["id"]


class ShippingRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ShippingRule
        fields = [
            "id", "name", "description", "method", "carrier",
            "estimated_days_min", "estimated_days_max", "is_additive",
            "flat_rate", "percentage_rate", "per_kg_rate",
            "free_threshold_amount", "max_charge",
            "conditions", "priority", "is_active", "start_date", "end_date",
        ]
        read_only_fields = ["id"]


class FeeRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model  = FeeRule
        fields = [
            "id", "name", "description", "fee_type", "amount_type",
            "amount", "is_negative", "max_amount",
            "conditions", "priority", "is_active", "start_date", "end_date",
        ]
        read_only_fields = ["id"]


class SurchargeLineItemSerializer(serializers.Serializer):
    name        = serializers.CharField()
    rule_type   = serializers.CharField()
    rule_id     = serializers.CharField()
    amount      = serializers.DecimalField(max_digits=12, decimal_places=2)
    rate        = serializers.DecimalField(max_digits=6, decimal_places=3, allow_null=True)
    is_negative = serializers.BooleanField()
    metadata    = serializers.DictField()


class SurchargeResultSerializer(serializers.Serializer):
    subtotal        = serializers.DecimalField(max_digits=12, decimal_places=2)
    tax_total       = serializers.DecimalField(max_digits=12, decimal_places=2)
    shipping_total  = serializers.DecimalField(max_digits=12, decimal_places=2)
    fee_total       = serializers.DecimalField(max_digits=12, decimal_places=2)
    discount_total  = serializers.DecimalField(max_digits=12, decimal_places=2)
    grand_total     = serializers.DecimalField(max_digits=12, decimal_places=2)
    breakdown       = SurchargeLineItemSerializer(many=True)


class CartSurchargeRequestSerializer(serializers.Serializer):
    shipping_address = serializers.DictField(child=serializers.CharField(allow_blank=True))
    payment_method   = serializers.CharField(required=False, default="")
    session_key      = serializers.CharField(required=False, default="")
