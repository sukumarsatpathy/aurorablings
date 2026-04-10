from rest_framework import serializers
from .models import Feature, FeatureFlag, ProviderConfig, AppSetting
from .security import mask_setting_value


class FeatureFlagSerializer(serializers.ModelSerializer):
    class Meta:
        model  = FeatureFlag
        fields = ["is_enabled", "rollout_percentage", "enabled_at", "disabled_at", "notes"]
        read_only_fields = ["enabled_at", "disabled_at"]


class FeatureSerializer(serializers.ModelSerializer):
    flag           = FeatureFlagSerializer(read_only=True)
    is_enabled     = serializers.SerializerMethodField()
    class Meta:
        model  = Feature
        fields = [
            "id", "code", "name", "description", "category", "tier",
            "requires_config", "config_schema", "is_available",
            "flag", "is_enabled", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_is_enabled(self, obj) -> bool:
        try:
            return obj.flag.is_enabled and obj.is_available
        except Exception:
            return False


class FeatureWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feature
        fields = [
            "code", "name", "description", "category", "tier",
            "requires_config", "config_schema", "is_available",
        ]


class ProviderConfigReadSerializer(serializers.ModelSerializer):
    masked_config = serializers.SerializerMethodField()
    feature_code  = serializers.CharField(source="feature.code", read_only=True)
    class Meta:
        model  = ProviderConfig
        fields = ["id", "feature_code", "provider_key", "masked_config", "is_active", "created_at", "updated_at"]
        read_only_fields = fields

    def get_masked_config(self, obj): return obj.masked_config()


class ProviderConfigWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ProviderConfig
        fields = ["provider_key", "config", "is_active"]


class AppSettingSerializer(serializers.ModelSerializer):
    typed_value = serializers.SerializerMethodField()

    class Meta:
        model  = AppSetting
        fields = [
            "id", "key", "value", "typed_value", "value_type",
            "category", "label", "description",
            "is_public", "is_editable", "updated_at",
        ]
        read_only_fields = ["id", "typed_value", "updated_at"]

    def get_typed_value(self, obj):
        return mask_setting_value(obj.key, obj.typed_value)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["value"] = mask_setting_value(instance.key, data.get("value"))
        data["typed_value"] = mask_setting_value(instance.key, data.get("typed_value"))
        return data


class AppSettingWriteSerializer(serializers.ModelSerializer):
    key = serializers.CharField(max_length=100)

    class Meta:
        model = AppSetting
        fields = [
            "key", "value", "value_type",
            "category", "label", "description",
            "is_public", "is_editable",
        ]


class PublicSettingSerializer(serializers.ModelSerializer):
    """Minimal serializer for unauthenticated public settings endpoint."""
    typed_value = serializers.SerializerMethodField()
    class Meta:
        model  = AppSetting
        fields = ["key", "label", "typed_value"]
    def get_typed_value(self, obj): return obj.typed_value


class PublicTrackingSettingsSerializer(serializers.Serializer):
    clarity_tracking_id = serializers.CharField(max_length=40, allow_blank=True)
    clarity_enabled = serializers.BooleanField()


# ── Write serializers ──────────────────────────────────────────

class EnableFeatureSerializer(serializers.Serializer):
    notes = serializers.CharField(required=False, default="")


class SetRolloutSerializer(serializers.Serializer):
    percentage = serializers.IntegerField(min_value=0, max_value=100)


class SetProviderConfigSerializer(serializers.Serializer):
    provider_key = serializers.SlugField()
    config       = serializers.DictField()
    activate     = serializers.BooleanField(default=True)


class ActivateProviderSerializer(serializers.Serializer):
    provider_key = serializers.SlugField()


class UpdateSettingSerializer(serializers.Serializer):
    value = serializers.CharField()


class BulkUpdateSettingsSerializer(serializers.Serializer):
    settings = serializers.DictField(child=serializers.CharField())
