from rest_framework import serializers

from .models import HealthAlert, HealthCheckResult


class HealthCheckResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = HealthCheckResult
        fields = (
            "id",
            "source",
            "component",
            "status",
            "response_time_ms",
            "message",
            "metadata",
            "checked_at",
        )


class HealthAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = HealthAlert
        fields = (
            "id",
            "component",
            "severity",
            "title",
            "message",
            "metadata",
            "is_resolved",
            "created_at",
            "resolved_at",
        )


class HealthSummarySerializer(serializers.Serializer):
    generated_at = serializers.DateTimeField()
    overall_status = serializers.CharField()
    total_components = serializers.IntegerField()
    status_distribution = serializers.DictField(child=serializers.IntegerField(min_value=0))
    source_distribution = serializers.DictField(child=serializers.IntegerField(min_value=0))
    open_alerts = serializers.IntegerField(min_value=0)
    resolved_alerts = serializers.IntegerField(min_value=0)
    latest_check_at = serializers.DateTimeField(allow_null=True)
    avg_response_time_ms = serializers.FloatField(allow_null=True)
