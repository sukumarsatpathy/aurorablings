from __future__ import annotations

from rest_framework import serializers

from audit.models import ActivityLog


class ActivityUserSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    email = serializers.EmailField(allow_blank=True)
    full_name = serializers.CharField(allow_blank=True)
    role = serializers.CharField(allow_blank=True)


class ActivityLogSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()

    class Meta:
        model = ActivityLog
        fields = [
            "id",
            "user",
            "actor_type",
            "action",
            "entity_type",
            "entity_id",
            "description",
            "metadata",
            "ip_address",
            "request_id",
            "path",
            "method",
            "created_at",
        ]
        read_only_fields = fields

    def get_user(self, obj: ActivityLog) -> dict | None:
        if not obj.user_id:
            return None

        user = obj.user
        return {
            "id": user.id,
            "email": getattr(user, "email", ""),
            "full_name": getattr(user, "full_name", "") or "",
            "role": getattr(user, "role", ""),
        }
