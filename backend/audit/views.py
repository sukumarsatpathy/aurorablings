from __future__ import annotations

from django_filters import rest_framework as filters
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from apps.accounts.permissions import IsStaffOrAdmin
from audit.models import ActivityLog
from audit.serializers import ActivityLogSerializer


class ActivityLogFilter(filters.FilterSet):
    user = filters.UUIDFilter(field_name="user_id")
    actor_type = filters.CharFilter(field_name="actor_type", lookup_expr="iexact")
    action = filters.CharFilter(field_name="action", lookup_expr="iexact")
    entity_type = filters.CharFilter(field_name="entity_type", lookup_expr="iexact")
    date_from = filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="gte")
    date_to = filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model = ActivityLog
        fields = ["user", "actor_type", "action", "entity_type", "date_from", "date_to"]


class ActivityLogListView(generics.ListAPIView):
    serializer_class = ActivityLogSerializer
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]
    queryset = ActivityLog.objects.select_related("user").all()
    filterset_class = ActivityLogFilter
    search_fields = ["description", "entity_id"]
    ordering_fields = ["created_at", "action", "entity_type"]
    ordering = ["-created_at"]
