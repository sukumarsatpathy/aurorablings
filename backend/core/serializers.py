from rest_framework import serializers
from .models import BaseModel, SoftDeleteModel


class BaseModelSerializer(serializers.ModelSerializer):
    """
    Base serializer for any model that extends BaseModel.

    Automatically exposes `id`, `created_at`, `updated_at` as
    read-only fields on all child serializers.

    Usage:
        class ProductSerializer(BaseModelSerializer):
            class Meta(BaseModelSerializer.Meta):
                model = Product
                fields = BaseModelSerializer.Meta.fields + ["name", "price"]
    """

    class Meta:
        model = BaseModel
        fields = ["id", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class SoftDeleteModelSerializer(BaseModelSerializer):
    """
    Extends BaseModelSerializer to expose `is_deleted` for soft-delete models.
    Use only on admin/internal endpoints — don't expose deletion state publicly.

    Usage:
        class ProductAdminSerializer(SoftDeleteModelSerializer):
            class Meta(SoftDeleteModelSerializer.Meta):
                model = Product
                fields = SoftDeleteModelSerializer.Meta.fields + ["name", "price"]
    """

    is_deleted = serializers.BooleanField(read_only=True)

    class Meta(BaseModelSerializer.Meta):
        model = SoftDeleteModel
        fields = BaseModelSerializer.Meta.fields + ["is_deleted", "deleted_at"]
        read_only_fields = BaseModelSerializer.Meta.read_only_fields + ["is_deleted", "deleted_at"]
