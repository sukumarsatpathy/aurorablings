import csv
from django.contrib import admin
from django.http import HttpResponse
from django.utils.html import format_html
from .models import (
    Notification,
    NotificationTemplate,
    NotificationLog,
    NotificationAttempt,
    NotificationStatus,
    NotifySubscription,
    ContactQuery,
    NotificationProviderSettings,
    EmailSettings,
    EmailLog,
)

STATUS_COLOURS = {
    NotificationStatus.PENDING:  "#d97706",
    NotificationStatus.SENT:     "#16a34a",
    NotificationStatus.FAILED:   "#dc2626",
    NotificationStatus.SKIPPED:  "#9ca3af",
}

CHANNEL_ICONS = {"email": "📧", "whatsapp": "💬", "sms": "📱", "push": "🔔"}


class NotificationLogInline(admin.TabularInline):
    model       = NotificationLog
    extra       = 0
    readonly_fields = ["attempt_number", "status", "recipient", "provider", "error_message", "attempted_at"]
    can_delete  = False
    def has_add_permission(self, request, obj=None): return False


class NotificationAttemptInline(admin.TabularInline):
    model = NotificationAttempt
    extra = 0
    readonly_fields = ["attempt_no", "status", "error_message", "provider_response", "created_at"]
    can_delete = False

    def has_add_permission(self, request, obj=None): return False


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display  = ["id_short", "channel_icon", "event_display", "status_badge", "recipient_display", "retry_display", "created_at"]
    list_filter   = ["status", "channel", "event_type", "event"]
    search_fields = ["recipient_email", "recipient_phone", "event", "event_type", "email", "user__email"]
    readonly_fields = [f.name for f in Notification._meta.fields]
    inlines       = [NotificationLogInline, NotificationAttemptInline]

    def has_add_permission(self, request): return False

    def id_short(self, obj): return str(obj.id)[:8] + "…"
    id_short.short_description = "ID"

    def channel_icon(self, obj): return CHANNEL_ICONS.get(obj.channel, "?") + " " + obj.channel
    channel_icon.short_description = "Channel"

    def event_display(self, obj):
        return obj.event_type or obj.event
    event_display.short_description = "Event"

    def status_badge(self, obj):
        colour = STATUS_COLOURS.get(obj.status, "#6b7280")
        return format_html('<span style="background:{};color:#fff;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:700">{}</span>', colour, obj.status.upper())
    status_badge.short_description = "Status"

    def recipient_display(self, obj): return obj.recipient_email or obj.recipient_phone
    recipient_display.short_description = "Recipient"

    def retry_display(self, obj):
        colour = "#dc2626" if obj.retry_count >= obj.max_retries else "#16a34a"
        return format_html('<span style="color:{}">{}/{}</span>', colour, obj.retry_count, obj.max_retries)
    retry_display.short_description = "Retries"

    actions = ["retry_selected"]

    def retry_selected(self, request, queryset):
        from .services import retry_notification
        count = 0
        for notif in queryset.filter(status="failed"):
            retry_notification(str(notif.id))
            count += 1
        self.message_user(request, f"{count} notification(s) queued for retry.")
    retry_selected.short_description = "Retry selected failed notifications"


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display  = ["name", "key", "event", "channel", "is_active", "updated_at"]
    list_filter   = ["is_active", "channel", "event", "key"]
    search_fields = ["name", "event", "key", "template_file"]
    readonly_fields = ["id", "created_at", "updated_at"]

    fieldsets = (
        ("Template", {"fields": ("id", "key", "name", "event", "channel", "is_active", "description")}),
        ("Content", {"fields": ("subject_template", "template_file", "body_template", "html_body_template")}),
        ("Meta", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(NotifySubscription)
class NotifySubscriptionAdmin(admin.ModelAdmin):
    list_display = ["product", "subscriber_display", "phone", "status_badge", "created_at"]
    list_filter = ["product", "is_notified", "is_active", ("created_at", admin.DateFieldListFilter)]
    date_hierarchy = "created_at"
    search_fields = ["product__name", "user__email", "email", "phone", "name"]
    autocomplete_fields = ["product"]
    readonly_fields = ["id", "unsubscribe_token", "created_at"]

    actions = ["mark_as_notified", "export_csv"]

    def subscriber_display(self, obj):
        if obj.user_id and obj.user:
            return obj.user.email
        if obj.email:
            return obj.email
        return "—"
    subscriber_display.short_description = "User / Email"

    def status_badge(self, obj):
        if obj.is_notified:
            return format_html(
                '<span style="background:#16a34a;color:#fff;padding:2px 8px;border-radius:999px;font-size:11px;font-weight:700">NOTIFIED</span>'
            )
        return format_html(
            '<span style="background:#d97706;color:#fff;padding:2px 8px;border-radius:999px;font-size:11px;font-weight:700">PENDING</span>'
        )
    status_badge.short_description = "Status"

    @admin.action(description="Mark selected subscriptions as notified")
    def mark_as_notified(self, request, queryset):
        updated = queryset.update(is_notified=True, is_active=False)
        self.message_user(request, f"{updated} subscription(s) marked as notified.")

    @admin.action(description="Export selected subscriptions as CSV")
    def export_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="notify_subscriptions.csv"'
        writer = csv.writer(response)
        writer.writerow(["Product", "User/Email", "Phone", "Status", "Created At"])
        for row in queryset.select_related("product", "user"):
            subscriber = row.user.email if row.user_id and row.user else row.email
            writer.writerow([
                row.product.name,
                subscriber,
                row.phone,
                "Notified" if row.is_notified else "Pending",
                row.created_at.isoformat(),
            ])
        return response


@admin.register(ContactQuery)
class ContactQueryAdmin(admin.ModelAdmin):
    list_display = ["name", "email", "phone", "subject", "status", "is_read", "created_at"]
    list_filter = ["status", "is_read", ("created_at", admin.DateFieldListFilter)]
    search_fields = ["name", "email", "phone", "subject", "message"]
    readonly_fields = ["id", "created_at", "updated_at", "read_at"]
    ordering = ["-created_at"]

    actions = ["mark_as_read", "mark_as_resolved"]

    @admin.action(description="Mark selected queries as read")
    def mark_as_read(self, request, queryset):
        from django.utils import timezone

        updated = queryset.filter(is_read=False).update(is_read=True, status="read", read_at=timezone.now())
        self.message_user(request, f"{updated} query(s) marked as read.")

    @admin.action(description="Mark selected queries as resolved")
    def mark_as_resolved(self, request, queryset):
        from django.utils import timezone

        updated = queryset.update(is_read=True, status="resolved", read_at=timezone.now())
        self.message_user(request, f"{updated} query(s) marked as resolved.")


@admin.register(EmailSettings)
class EmailSettingsAdmin(admin.ModelAdmin):
    list_display = ["smtp_host", "smtp_port", "smtp_user", "from_email", "enabled", "updated_at"]
    fieldsets = (
        ("SMTP", {"fields": ("smtp_host", "smtp_port", "smtp_user", "smtp_password", "use_tls", "enabled")}),
        ("Sender", {"fields": ("from_email",)}),
    )

    def has_add_permission(self, request):
        # Singleton settings row
        if EmailSettings.objects.exists():
            return False
        return super().has_add_permission(request)


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ["created_at", "email_type", "recipient", "status", "user"]
    list_filter = ["status", "email_type", ("created_at", admin.DateFieldListFilter)]
    search_fields = ["recipient", "email_type", "user__email", "error_message"]
    readonly_fields = [field.name for field in EmailLog._meta.fields]

    def has_add_permission(self, request):
        return False


@admin.register(NotificationProviderSettings)
class NotificationProviderSettingsAdmin(admin.ModelAdmin):
    list_display = [
        "provider_type",
        "is_active",
        "last_test_status",
        "last_tested_at",
        "updated_at",
    ]
    search_fields = ["provider_type", "last_test_message"]
    readonly_fields = ["updated_at", "last_tested_at", "last_test_status", "last_test_message"]
