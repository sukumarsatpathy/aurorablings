from rest_framework import serializers

from .models import (
    ContactQuery,
    Notification,
    NotificationLog,
    NotificationProviderSettings,
    NotificationTemplate,
    NotifySubscription,
)


class NotificationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationLog
        fields = ["id", "attempt_number", "success", "provider_ref", "error", "attempted_at"]
        read_only_fields = fields


class NotificationSerializer(serializers.ModelSerializer):
    logs = NotificationLogSerializer(many=True, read_only=True)
    attempts = serializers.SerializerMethodField()
    event_type = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id",
            "event",
            "event_type",
            "channel",
            "recipient_email",
            "recipient_phone",
            "email",
            "subject",
            "body",
            "status",
            "provider_ref",
            "retry_count",
            "max_retries",
            "can_retry",
            "send_at",
            "sent_at",
            "last_error",
            "created_at",
            "logs",
            "attempts",
            "payload",
            "error_message",
            "subject_snapshot",
            "template_key",
        ]
        read_only_fields = fields

    can_retry = serializers.BooleanField(read_only=True)

    def get_event_type(self, obj):
        return obj.event_type or obj.event

    def get_attempts(self, obj):
        return [
            {
                "id": str(attempt.id),
                "attempt_no": attempt.attempt_no,
                "status": attempt.status,
                "error_message": attempt.error_message,
                "provider_response": attempt.provider_response,
                "created_at": attempt.created_at,
            }
            for attempt in obj.attempts.all().order_by("-created_at")[:10]
        ]


class NotificationTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationTemplate
        fields = [
            "id",
            "key",
            "code",
            "event",
            "channel",
            "name",
            "subject_template",
            "template_file",
            "description",
            "body_template",
            "html_body_template",
            "html_template",
            "text_template",
            "version",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class TriggerEventSerializer(serializers.Serializer):
    event = serializers.CharField()
    recipient_email = serializers.EmailField(required=False, default="")
    recipient_phone = serializers.CharField(required=False, default="")
    context = serializers.JSONField(required=False, default=dict)


class ContactFormSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    subject = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    message = serializers.CharField()
    turnstile_token = serializers.CharField(required=False, allow_blank=True, write_only=True)


class AdminContactQuerySerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactQuery
        fields = [
            "id",
            "name",
            "email",
            "phone",
            "subject",
            "message",
            "status",
            "is_read",
            "source",
            "created_at",
            "updated_at",
            "read_at",
        ]
        read_only_fields = fields


class NotifySubscriptionWriteSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")

    def validate(self, attrs):
        attrs["name"] = (attrs.get("name") or "").strip()
        attrs["email"] = (attrs.get("email") or "").strip().lower()
        attrs["phone"] = (attrs.get("phone") or "").strip()

        request = self.context.get("request")
        is_authenticated = bool(request and getattr(request, "user", None) and request.user.is_authenticated)
        if not is_authenticated and not attrs["email"]:
            raise serializers.ValidationError({"email": ["Email is required for guest subscriptions."]})
        return attrs


class NotifySubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotifySubscription
        fields = ["id", "product", "user", "name", "email", "phone", "is_notified", "is_active", "created_at"]
        read_only_fields = fields


class AdminNotifySubscriptionSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    user_email = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = NotifySubscription
        fields = [
            "id",
            "product",
            "product_name",
            "user",
            "user_email",
            "name",
            "email",
            "phone",
            "is_notified",
            "is_active",
            "status",
            "created_at",
        ]
        read_only_fields = fields

    def get_user_email(self, obj):
        if obj.user_id and obj.user:
            return obj.user.email
        return ""

    def get_status(self, obj):
        return "Notified" if obj.is_notified else "Pending"


class NotificationLogListSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationLog
        fields = [
            "id",
            "created_at",
            "channel",
            "notification_type",
            "recipient",
            "subject",
            "provider",
            "status",
            "attempts_count",
            "error_message",
        ]


class NotificationLogDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationLog
        fields = [
            "id",
            "channel",
            "notification_type",
            "recipient",
            "subject",
            "provider",
            "provider_message_id",
            "status",
            "template_name",
            "rendered_context_json",
            "rendered_html_snapshot",
            "plain_text_snapshot",
            "error_message",
            "error_code",
            "attempts_count",
            "last_attempt_at",
            "sent_at",
            "created_at",
            "created_by",
            "related_object_type",
            "related_object_id",
            "notification",
            "attempt_number",
            "success",
            "provider_ref",
            "error",
            "raw_response",
            "attempted_at",
        ]


class ProviderStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationProviderSettings
        fields = [
            "id",
            "provider_type",
            "is_active",
            "last_tested_at",
            "last_test_status",
            "last_test_message",
            "updated_at",
        ]


class TemplateUsageSerializer(serializers.Serializer):
    template_code = serializers.CharField()
    sends = serializers.IntegerField()
    success_count = serializers.IntegerField()
    failure_count = serializers.IntegerField()
    last_used = serializers.DateTimeField(allow_null=True)


class NotificationDashboardSerializer(serializers.Serializer):
    stats = serializers.DictField()
    provider_status = ProviderStatusSerializer(many=True)
    recent_failures = NotificationLogListSerializer(many=True)
    template_usage = TemplateUsageSerializer(many=True)
