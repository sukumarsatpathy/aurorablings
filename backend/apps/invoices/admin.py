from django.contrib import admin
from django.utils.html import format_html

from .models import Invoice


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ["invoice_number", "order", "generated_at", "file_link", "created_at"]
    search_fields = ["invoice_number", "order__order_number", "order__user__email", "order__guest_email"]
    readonly_fields = ["id", "invoice_number", "generated_at", "file_size", "created_at", "updated_at", "file_link"]

    def file_link(self, obj):
        if not obj.file:
            return "-"
        return format_html('<a href="{}" target="_blank">Download</a>', obj.file.url)

    file_link.short_description = "File"
