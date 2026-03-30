from django.contrib import admin

from audit.models import ActivityLog


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = [
        "created_at",
        "actor_type",
        "action",
        "entity_type",
        "entity_id",
        "user",
        "request_id",
    ]
    list_filter = ["actor_type", "action", "entity_type", "created_at"]
    search_fields = ["description", "entity_id", "request_id", "path", "user__email"]
    date_hierarchy = "created_at"
    ordering = ["-created_at"]
    readonly_fields = [field.name for field in ActivityLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
