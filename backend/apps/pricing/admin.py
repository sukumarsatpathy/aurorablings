from django.contrib import admin

from .models import Coupon, CouponUsage


class CouponUsageInline(admin.TabularInline):
    model = CouponUsage
    extra = 0
    fields = ["user", "cart", "order", "discount_amount", "used_at"]
    readonly_fields = ["user", "cart", "order", "discount_amount", "used_at"]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = [
        "code",
        "type",
        "value",
        "max_discount",
        "min_order_value",
        "usage_limit",
        "per_user_limit",
        "is_active",
        "start_date",
        "end_date",
        "created_at",
    ]
    list_filter = ["type", "is_active", "start_date", "end_date", "created_at"]
    search_fields = ["code"]
    ordering = ["-created_at"]
    readonly_fields = ["id", "created_at", "updated_at"]
    inlines = [CouponUsageInline]

    fieldsets = (
        ("Coupon", {"fields": ("id", "code", "type", "value", "is_active")}),
        (
            "Rules",
            {
                "fields": (
                    "max_discount",
                    "min_order_value",
                    "usage_limit",
                    "per_user_limit",
                )
            },
        ),
        ("Validity", {"fields": ("start_date", "end_date")}),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


@admin.register(CouponUsage)
class CouponUsageAdmin(admin.ModelAdmin):
    list_display = ["coupon", "user", "order", "cart", "discount_amount", "used_at"]
    list_filter = ["coupon", "used_at"]
    search_fields = ["coupon__code", "order__order_number", "cart__id", "user__email"]
    readonly_fields = [f.name for f in CouponUsage._meta.fields]
    ordering = ["-used_at"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
