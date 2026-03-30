from django.contrib import admin
from .models import PromoBanner

@admin.register(PromoBanner)
class PromoBannerAdmin(admin.ModelAdmin):
    list_display = ['position', 'title', 'order', 'is_active', 'updated_at']
    list_filter = ['is_active', 'position']
    search_fields = ['title', 'badge_text']
    ordering = ['order']
