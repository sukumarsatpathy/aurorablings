from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Q
from .models import (
    Category, Brand, Product, ProductMedia,
    Attribute, AttributeValue, ProductVariant, VariantAttributeValue,
    GlobalAttribute, GlobalAttributeOption, ProductAttributeConfig, ProductInfoItem,
    ProductStockNotifyRequest,
)


# ─────────────────────────────────────────────────────────────
#  Category
# ─────────────────────────────────────────────────────────────

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display  = ["name", "parent", "is_active", "sort_order", "created_at"]
    list_filter   = ["is_active", "parent"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    ordering = ["sort_order", "name"]


# ─────────────────────────────────────────────────────────────
#  Brand
# ─────────────────────────────────────────────────────────────

@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display  = ["name", "slug", "is_active"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ("name",)}


# ─────────────────────────────────────────────────────────────
#  Product Media Inline
# ─────────────────────────────────────────────────────────────

class ProductMediaInline(admin.TabularInline):
    model      = ProductMedia
    extra      = 1
    fields     = ["image", "image_preview", "alt_text", "is_primary", "sort_order"]
    readonly_fields = ["image_preview"]

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" height="60" style="border-radius:4px"/>', obj.image.url)
        return "—"
    image_preview.short_description = "Preview"


# ─────────────────────────────────────────────────────────────
#  Variant Attribute Value Inline
# ─────────────────────────────────────────────────────────────

class VariantAttributeValueInline(admin.TabularInline):
    model = VariantAttributeValue
    extra = 1


# ─────────────────────────────────────────────────────────────
#  Product Variant Inline
# ─────────────────────────────────────────────────────────────

class ProductVariantInline(admin.TabularInline):
    model  = ProductVariant
    extra  = 1
    fields = [
        "sku", "price", "offer_price", "offer_starts_at", "offer_ends_at",
        "compare_at_price", "stock_quantity", "is_default", "is_active",
    ]
    show_change_link = True


class ProductInfoItemInline(admin.TabularInline):
    model = ProductInfoItem
    extra = 1
    fields = ["title", "value", "sort_order", "is_active"]


# ─────────────────────────────────────────────────────────────
#  Attribute Inline
# ─────────────────────────────────────────────────────────────

class AttributeValueInline(admin.TabularInline):
    model = AttributeValue
    extra = 2
    fields = ["value", "sort_order"]


class AttributeInline(admin.TabularInline):
    model = Attribute
    extra = 1
    fields = ["name", "sort_order"]
    show_change_link = True


# ─────────────────────────────────────────────────────────────
#  Product
# ─────────────────────────────────────────────────────────────

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display   = [
        "name", "category", "brand", "is_active", "is_featured",
        "variant_count", "notify_waiting_count", "price_display", "created_at",
    ]
    list_filter    = ["is_active", "is_featured", "category", "brand"]
    search_fields  = ["name", "slug", "variants__sku"]
    prepopulated_fields = {"slug": ("name",)}
    inlines        = [ProductMediaInline, ProductInfoItemInline, AttributeInline, ProductVariantInline]

    fieldsets = (
        ("Identity", {
            "fields": ("name", "slug", "category", "brand", "short_description", "description"),
        }),
        ("Demand Signals", {
            "fields": ("notify_waiting_count",),
        }),
        ("Status", {
            "fields": ("is_active", "is_featured", "is_digital"),
        }),
        ("SEO", {
            "fields": ("meta_title", "meta_description"),
            "classes": ("collapse",),
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    readonly_fields = ["created_at", "updated_at", "notify_waiting_count"]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            notify_waiting_total=Count(
                "notify_subscriptions",
                filter=Q(
                    notify_subscriptions__is_active=True,
                    notify_subscriptions__is_notified=False,
                ),
                distinct=True,
            )
        )

    def variant_count(self, obj):
        return obj.variants.count()
    variant_count.short_description = "Variants"

    def price_display(self, obj):
        pr = obj.price_range
        if pr["min"] is None:
            return "—"
        if pr["min"] == pr["max"]:
            return f"₹{pr['min']}"
        return f"₹{pr['min']} – ₹{pr['max']}"
    price_display.short_description = "Price"

    def notify_waiting_count(self, obj):
        count = int(getattr(obj, "notify_waiting_total", 0))
        return f"{count} users waiting for this product"
    notify_waiting_count.short_description = "Users Waiting"


# ─────────────────────────────────────────────────────────────
#  Product Variant
# ─────────────────────────────────────────────────────────────

@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display   = [
        "sku", "product", "price", "offer_price", "offer_starts_at", "offer_ends_at",
        "compare_at_price", "stock_quantity", "is_default", "is_active",
    ]
    list_filter    = ["is_active", "is_default", "product__category"]
    search_fields  = ["sku", "product__name"]
    inlines        = [VariantAttributeValueInline]
    readonly_fields = ["created_at", "updated_at"]


# ─────────────────────────────────────────────────────────────
#  Attribute
# ─────────────────────────────────────────────────────────────

@admin.register(Attribute)
class AttributeAdmin(admin.ModelAdmin):
    list_display = ["name", "product", "sort_order"]
    search_fields = ["name", "product__name"]
    inlines = [AttributeValueInline]


class GlobalAttributeOptionInline(admin.TabularInline):
    model = GlobalAttributeOption
    extra = 1
    fields = ["value", "sort_order", "is_active"]


@admin.register(GlobalAttribute)
class GlobalAttributeAdmin(admin.ModelAdmin):
    list_display = ["name", "sort_order", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name"]
    inlines = [GlobalAttributeOptionInline]


@admin.register(ProductAttributeConfig)
class ProductAttributeConfigAdmin(admin.ModelAdmin):
    list_display = ["product", "global_attribute", "sort_order", "is_active"]
    list_filter = ["is_active", "global_attribute"]
    search_fields = ["product__name", "global_attribute__name"]


@admin.register(ProductStockNotifyRequest)
class ProductStockNotifyRequestAdmin(admin.ModelAdmin):
    list_display = [
        "product",
        "variant",
        "contact_display",
        "quantity",
        "is_notified",
        "created_at",
    ]
    list_filter = ["is_notified", "product__category"]
    search_fields = ["product__name", "variant__sku", "email", "phone", "name"]
    autocomplete_fields = ["product", "variant"]
    readonly_fields = ["created_at", "updated_at"]

    def contact_display(self, obj):
        if obj.user_id and obj.user:
            return obj.user.email
        if obj.email:
            return obj.email
        if obj.phone:
            return obj.phone
        return "—"
    contact_display.short_description = "Contact"
