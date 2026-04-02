from __future__ import annotations

from rest_framework import serializers

from .models import ConsentSource, ConsentStatus


class CookieConsentSerializer(serializers.Serializer):
    anonymous_id = serializers.CharField(max_length=128, required=False, allow_blank=True)
    session_id = serializers.CharField(max_length=128, required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=ConsentStatus.choices)
    version = serializers.CharField(max_length=32, default="1.0")
    source = serializers.ChoiceField(choices=ConsentSource.choices)
    categories = serializers.DictField(child=serializers.BooleanField(), required=True)

    def validate_categories(self, value: dict) -> dict:
        required_keys = {"necessary", "analytics", "marketing", "preferences"}
        if not required_keys.issubset(set(value.keys())):
            raise serializers.ValidationError("categories must include necessary, analytics, marketing, and preferences")

        value["necessary"] = True
        value["analytics"] = bool(value.get("analytics", False))
        value["marketing"] = bool(value.get("marketing", False))
        value["preferences"] = bool(value.get("preferences", False))
        return value

    def validate(self, attrs: dict) -> dict:
        categories = attrs["categories"]
        status = attrs["status"]

        if categories.get("necessary") is not True:
            raise serializers.ValidationError({"categories": "necessary must always be true"})

        optional_enabled = [
            categories["analytics"],
            categories["marketing"],
            categories["preferences"],
        ]

        if status == ConsentStatus.ACCEPTED_ALL and not all(optional_enabled):
            raise serializers.ValidationError({"status": "accepted_all requires all optional categories enabled"})

        if status == ConsentStatus.REJECTED_ALL and any(optional_enabled):
            raise serializers.ValidationError({"status": "rejected_all requires all optional categories disabled"})

        return attrs


class CookieConsentCurrentSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    anonymous_id = serializers.CharField(read_only=True)
    session_id = serializers.CharField(read_only=True)
    consent_status = serializers.CharField(read_only=True)
    consent_version = serializers.CharField(read_only=True)
    source = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    categories = serializers.SerializerMethodField()

    def get_categories(self, obj):
        return {
            "necessary": obj.category_necessary,
            "analytics": obj.category_analytics,
            "marketing": obj.category_marketing,
            "preferences": obj.category_preferences,
        }
