from django.contrib import admin
from django.utils.html import format_html

from .models import ProductReview, ReviewMedia
from .services import moderate_review


class ReviewMediaInline(admin.TabularInline):
    model = ReviewMedia
    extra = 0
    fields = ["image", "image_preview", "sort_order", "created_at"]
    readonly_fields = ["image_preview", "created_at"]

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" height="60" style="border-radius:4px"/>', obj.image.url)
        return "—"

    image_preview.short_description = "Preview"


@admin.action(description="Approve selected reviews")
def approve_selected(modeladmin, request, queryset):
    for review in queryset:
        moderate_review(review=review, moderator=request.user, action="approve")


@admin.action(description="Reject selected reviews")
def reject_selected(modeladmin, request, queryset):
    for review in queryset:
        moderate_review(review=review, moderator=request.user, action="reject")


@admin.action(description="Hide selected reviews")
def hide_selected(modeladmin, request, queryset):
    for review in queryset:
        moderate_review(review=review, moderator=request.user, action="hide")


@admin.action(description="Feature selected reviews")
def feature_selected(modeladmin, request, queryset):
    for review in queryset:
        if review.status == "approved":
            moderate_review(review=review, moderator=request.user, action="feature", is_featured=True)


@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    list_display = [
        "product",
        "user",
        "rating",
        "status",
        "is_verified_purchase",
        "is_featured",
        "created_at",
    ]
    list_filter = [
        "status",
        "rating",
        "is_verified_purchase",
        "is_featured",
        "created_at",
    ]
    search_fields = [
        "product__name",
        "user__email",
        "user__first_name",
        "user__last_name",
        "title",
        "comment",
    ]
    readonly_fields = ["created_at", "updated_at", "moderated_at"]
    inlines = [ReviewMediaInline]
    actions = [approve_selected, reject_selected, hide_selected, feature_selected]
