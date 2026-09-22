from __future__ import annotations

from rest_framework import serializers

from .models import Coupon


class CouponSerializer(serializers.ModelSerializer):
    discount_type = serializers.CharField(source="type", required=False)
    min_order_amount = serializers.DecimalField(source="min_order_value", max_digits=12, decimal_places=2, required=False)
    valid_from = serializers.DateTimeField(source="start_date", required=False)
    valid_to = serializers.DateTimeField(source="end_date", required=False)
    assigned_user_email = serializers.EmailField(source="assigned_user.email", read_only=True)

    class Meta:
        model = Coupon
        fields = [
            "id",
            "code",
            "type",
            "discount_type",
            "value",
            "max_discount",
            "min_order_value",
            "min_order_amount",
            "usage_limit",
            "per_user_limit",
            "start_date",
            "end_date",
            "valid_from",
            "valid_to",
            "is_active",
            "assigned_user",
            "assigned_user_email",
            "occasion",
            "occasion_year",
            "created_at",
            "updated_at",
        ]
        # Personal coupons are minted by the occasion sweep, never by hand: an
        # admin assigning one through this form would bypass the per-user /
        # per-year uniqueness the sweep relies on.
        read_only_fields = [
            "id", "created_at", "updated_at",
            "assigned_user", "assigned_user_email", "occasion", "occasion_year",
        ]

    def validate_code(self, value: str) -> str:
        return value.strip().upper()

    def validate(self, attrs):
        instance = getattr(self, "instance", None)

        coupon_type = attrs.get("type", getattr(instance, "type", None))
        value = attrs.get("value", getattr(instance, "value", None))
        start_date = attrs.get("start_date", getattr(instance, "start_date", None))
        end_date = attrs.get("end_date", getattr(instance, "end_date", None))
        usage_limit = attrs.get("usage_limit", getattr(instance, "usage_limit", None))
        per_user_limit = attrs.get("per_user_limit", getattr(instance, "per_user_limit", None))

        if coupon_type == "percentage" and value is not None and value > 100:
            raise serializers.ValidationError({"value": "Percentage coupon value cannot exceed 100."})

        if start_date and end_date and end_date <= start_date:
            raise serializers.ValidationError({"end_date": "End date must be later than start date."})

        if usage_limit is not None and per_user_limit is not None and per_user_limit > usage_limit:
            raise serializers.ValidationError(
                {"per_user_limit": "Per-user limit cannot exceed the total usage limit."}
            )

        return attrs
