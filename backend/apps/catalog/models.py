"""
catalog.models
~~~~~~~~~~~~~~
Full catalog model hierarchy:

  Category (tree-ish, parent FK)
  └── Brand
  └── Product  (extends SoftDeleteModel)
       ├── ProductMedia
       ├── Attribute  (Size, Color, Material …)
       │    └── AttributeValue (S, M, L / Red, Blue …)
       └── ProductVariant
            └── VariantAttributeValue (M2M through table)
"""

import uuid
from django.db import models
from django.conf import settings
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator

from core.models import SoftDeleteModel, BaseModel
from core.image_optimization import compress_image, generate_responsive_variants
from .managers import PublishedManager, ActiveCategoryManager


# ─────────────────────────────────────────────────────────────
#  Category
# ─────────────────────────────────────────────────────────────

class Category(BaseModel):
    """
    Self-referential category tree.
    e.g. Jewellery → Rings → Diamond Rings
    """

    name      = models.CharField(max_length=200, db_index=True)
    slug      = models.SlugField(max_length=220, unique=True, db_index=True)
    parent    = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="children",
    )
    image     = models.ImageField(upload_to="categories/", blank=True, null=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    objects     = ActiveCategoryManager()
    all_objects = models.Manager()

    class Meta:
        verbose_name        = _("category")
        verbose_name_plural = _("categories")
        ordering            = ["sort_order", "name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def full_path(self) -> str:
        """Returns 'Jewellery > Rings > Diamond Rings'."""
        if self.parent:
            return f"{self.parent.full_path} > {self.name}"
        return self.name

    def __str__(self):
        return self.full_path


# ─────────────────────────────────────────────────────────────
#  Brand
# ─────────────────────────────────────────────────────────────

class Brand(BaseModel):
    name      = models.CharField(max_length=200, unique=True, db_index=True)
    slug      = models.SlugField(max_length=220, unique=True)
    logo      = models.ImageField(upload_to="brands/", blank=True, null=True)
    website   = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name        = _("brand")
        verbose_name_plural = _("brands")
        ordering            = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


# ─────────────────────────────────────────────────────────────
#  Product
# ─────────────────────────────────────────────────────────────

class Product(SoftDeleteModel):
    """
    Core product entity.

    Pricing lives on ProductVariant — a product without variants
    should have exactly one "default" variant.
    """

    # ── Identity ──────────────────────────────────────────────
    name        = models.CharField(max_length=255, db_index=True)
    slug        = models.SlugField(max_length=280, unique=True, db_index=True)
    description = models.TextField(blank=True)
    short_description = models.CharField(max_length=500, blank=True)

    # ── Relations ─────────────────────────────────────────────
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
    )
    brand = models.ForeignKey(
        Brand,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="products",
    )

    # ── Status ────────────────────────────────────────────────
    is_active   = models.BooleanField(default=True, db_index=True)
    is_featured = models.BooleanField(default=False, db_index=True)
    is_digital  = models.BooleanField(default=False)
    rating      = models.DecimalField(
        max_digits=3, decimal_places=2, default=0.0,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
        help_text="Product rating from 0 to 5."
    )
    avg_rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0.0,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
        help_text="Average rating based on approved reviews only.",
    )
    review_count = models.PositiveIntegerField(default=0)

    # ── SEO ───────────────────────────────────────────────────
    meta_title       = models.CharField(max_length=255, blank=True)
    meta_description = models.CharField(max_length=500, blank=True)

    # ── Managers ──────────────────────────────────────────────
    published   = PublishedManager()    # active + not deleted
    all_objects = models.Manager()      # unfiltered

    class Meta:
        verbose_name        = _("product")
        verbose_name_plural = _("products")
        ordering            = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)
            self.slug = self._unique_slug(base)
        super().save(*args, **kwargs)

    def _unique_slug(self, base: str) -> str:
        slug, n = base, 1
        while Product.all_objects.filter(slug=slug).exists():
            slug = f"{base}-{n}"
            n += 1
        return slug

    @property
    def default_variant(self):
        return self.variants.filter(is_default=True).first()

    @property
    def price_range(self) -> dict:
        prices = [v.effective_price for v in self.variants.filter(is_active=True)]
        if not prices:
            return {"min": None, "max": None}
        return {"min": min(prices), "max": max(prices)}

    def __str__(self):
        return self.name


# ─────────────────────────────────────────────────────────────
#  Product Additional Information
# ─────────────────────────────────────────────────────────────

class ProductInfoItem(BaseModel):
    """
    Additional product information rows displayed on the product detail tab.
    Example: "Weight" -> "500g"
    """

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="info_items",
    )
    title = models.CharField(max_length=120, db_index=True)
    value = models.TextField()
    sort_order = models.PositiveIntegerField(default=0, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        verbose_name = _("product info item")
        verbose_name_plural = _("product info items")
        ordering = ["sort_order", "created_at"]

    def __str__(self):
        return f"{self.product.name} — {self.title}"


# ─────────────────────────────────────────────────────────────
#  Product Stock Notify Requests
# ─────────────────────────────────────────────────────────────

class ProductStockNotifyRequest(BaseModel):
    """
    Customer interest records for out-of-stock products.
    Used to track who wants to be notified when stock returns.
    """

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="stock_notify_requests",
    )
    variant = models.ForeignKey(
        "ProductVariant",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="stock_notify_requests",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="stock_notify_requests",
    )
    name = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True, db_index=True)
    phone = models.CharField(max_length=20, blank=True, db_index=True)
    quantity = models.PositiveIntegerField(default=1)
    notes = models.CharField(max_length=255, blank=True)
    is_notified = models.BooleanField(default=False, db_index=True)

    class Meta:
        verbose_name = _("product stock notify request")
        verbose_name_plural = _("product stock notify requests")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["product", "created_at"]),
            models.Index(fields=["variant", "created_at"]),
            models.Index(fields=["user", "created_at"]),
        ]

    def __str__(self):
        target = self.variant.sku if self.variant_id and self.variant else "product"
        who = self.email or self.phone or (self.user.email if self.user_id else "anonymous")
        return f"{self.product.name} [{target}] -> {who}"


# ─────────────────────────────────────────────────────────────
#  Product Media
# ─────────────────────────────────────────────────────────────

class ProductMedia(BaseModel):
    """
    Ordered images for a product.
    One image can be flagged `is_primary` — shown as the main thumbnail.
    """

    product    = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="media")
    image      = models.ImageField(upload_to="products/%Y/%m/")
    image_small = models.ImageField(upload_to="products/%Y/%m/", blank=True, null=True)
    image_medium = models.ImageField(upload_to="products/%Y/%m/", blank=True, null=True)
    image_large = models.ImageField(upload_to="products/%Y/%m/", blank=True, null=True)
    alt_text   = models.CharField(max_length=255, blank=True)
    is_primary = models.BooleanField(default=False, db_index=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name        = _("product media")
        verbose_name_plural = _("product media")
        ordering            = ["sort_order", "-is_primary"]

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        should_generate = bool(self.image) and (
            not self.pk
            or not self.image_small
            or not self.image_medium
            or not self.image_large
            or (update_fields is not None and "image" in update_fields)
        )

        if should_generate:
            src_name = getattr(self.image, "name", "") or ""
            parent_dir = "/".join(src_name.split("/")[:-1]) or "products"
            stem = src_name.rsplit("/", 1)[-1].rsplit(".", 1)[0] if src_name else None
            main_name, main_content = compress_image(
                self.image,
                output_dir=parent_dir,
                max_width=1800,
                quality=74,
                file_stem=stem,
            )
            self.image.save(main_name, main_content, save=False)
            base_stem = main_name.rsplit("/", 1)[-1].rsplit(".", 1)[0]
            variants = generate_responsive_variants(
                self.image,
                output_dir=parent_dir,
                base_stem=base_stem,
                widths=(480, 768, 1200),
                quality=72,
            )
            small_name, small_content = variants["small"]
            medium_name, medium_content = variants["medium"]
            large_name, large_content = variants["large"]
            self.image_small.save(small_name, small_content, save=False)
            self.image_medium.save(medium_name, medium_content, save=False)
            self.image_large.save(large_name, large_content, save=False)

        # Enforce only one primary per product
        if self.is_primary:
            ProductMedia.objects.filter(
                product=self.product, is_primary=True
            ).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name} — media {self.sort_order}"


# ─────────────────────────────────────────────────────────────
#  Attributes & Values
# ─────────────────────────────────────────────────────────────

class Attribute(BaseModel):
    """
    A variant dimension — e.g. 'Size', 'Color', 'Material'.
    An attribute belongs to a product; attribute values belong to an attribute.
    """

    product    = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="attributes",
    )
    name       = models.CharField(max_length=100)      # e.g. "Color"
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name        = _("attribute")
        verbose_name_plural = _("attributes")
        unique_together     = [("product", "name")]
        ordering            = ["sort_order", "name"]

    def __str__(self):
        return f"{self.product.name} — {self.name}"


class AttributeValue(BaseModel):
    """
    A concrete value for an attribute — e.g. 'Color: Red', 'Size: M'.
    """

    attribute  = models.ForeignKey(
        Attribute,
        on_delete=models.CASCADE,
        related_name="values",
    )
    value      = models.CharField(max_length=100)      # e.g. "Red"
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name        = _("attribute value")
        verbose_name_plural = _("attribute values")
        unique_together     = [("attribute", "value")]
        ordering            = ["sort_order", "value"]

    def __str__(self):
        return f"{self.attribute.name}: {self.value}"


# ─────────────────────────────────────────────────────────────
#  Global Attributes (shared across products)
# ─────────────────────────────────────────────────────────────

class GlobalAttribute(BaseModel):
    """
    Global attribute dimension reusable across products.
    e.g. Size, Color, Material.
    """

    name = models.CharField(max_length=100, unique=True, db_index=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        verbose_name = _("global attribute")
        verbose_name_plural = _("global attributes")
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


class GlobalAttributeOption(BaseModel):
    """
    Global option value for a global attribute.
    e.g. Size -> S, M, L.
    """

    global_attribute = models.ForeignKey(
        GlobalAttribute,
        on_delete=models.CASCADE,
        related_name="options",
    )
    value = models.CharField(max_length=100)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        verbose_name = _("global attribute option")
        verbose_name_plural = _("global attribute options")
        unique_together = [("global_attribute", "value")]
        ordering = ["sort_order", "value"]

    def __str__(self):
        return f"{self.global_attribute.name}: {self.value}"


class ProductAttributeConfig(BaseModel):
    """
    Links a product to a global attribute that should be available
    for variant generation/selection on that product.
    """

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="global_attribute_configs",
    )
    global_attribute = models.ForeignKey(
        GlobalAttribute,
        on_delete=models.CASCADE,
        related_name="product_configs",
    )
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        verbose_name = _("product attribute config")
        verbose_name_plural = _("product attribute configs")
        unique_together = [("product", "global_attribute")]
        ordering = ["sort_order", "global_attribute__name"]

    def __str__(self):
        return f"{self.product.name} — {self.global_attribute.name}"


# ─────────────────────────────────────────────────────────────
#  Product Variant
# ─────────────────────────────────────────────────────────────

class ProductVariant(BaseModel):
    """
    A purchasable combination of attribute values for a product.

    Every product must have at least one variant.
    Pricing is MANDATORY at the variant level.
    """

    product    = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="variants",
    )

    # ── Identity ──────────────────────────────────────────────
    sku        = models.CharField(max_length=100, unique=True, db_index=True)
    name       = models.CharField(
        max_length=255, blank=True,
        help_text="Auto-generated from attribute values if left blank."
    )

    # ── Pricing (mandatory, no null allowed) ─────────────────
    price            = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    offer_price      = models.DecimalField(
        max_digits=12, decimal_places=2,
        null=True, blank=True,
        validators=[MinValueValidator(0)],
        help_text="Limited-time offer price.",
    )
    offer_starts_at  = models.DateTimeField(
        null=True, blank=True,
        help_text="Offer starts at this datetime.",
    )
    offer_ends_at    = models.DateTimeField(
        null=True, blank=True,
        help_text="Offer ends at this datetime.",
    )
    offer_label      = models.CharField(
        max_length=80, blank=True,
        help_text="Optional label like 'Flash Sale'.",
    )
    offer_is_active  = models.BooleanField(
        default=False,
        help_text="Master switch for offer availability.",
    )
    compare_at_price = models.DecimalField(
        max_digits=12, decimal_places=2,
        null=True, blank=True,
        validators=[MinValueValidator(0)],
        help_text="Original / crossed-out price shown to indicate discount.",
    )
    cost_price = models.DecimalField(
        max_digits=12, decimal_places=2,
        null=True, blank=True,
        validators=[MinValueValidator(0)],
        help_text="Internal cost — not exposed via public API.",
    )

    # ── Inventory placeholder ─────────────────────────────────
    stock_quantity = models.IntegerField(default=0)
    low_stock_threshold = models.PositiveSmallIntegerField(default=5)
    track_inventory = models.BooleanField(default=True)
    allow_backorder = models.BooleanField(default=False)

    # ── Flags ─────────────────────────────────────────────────
    is_active  = models.BooleanField(default=True, db_index=True)
    is_default = models.BooleanField(default=False, db_index=True)

    # ── Physical attributes (for shipping) ────────────────────
    weight_grams = models.PositiveIntegerField(null=True, blank=True)

    # ── Attribute values (the variant's "combination") ────────
    attribute_values = models.ManyToManyField(
        AttributeValue,
        through="VariantAttributeValue",
        related_name="variants",
    )

    class Meta:
        verbose_name        = _("product variant")
        verbose_name_plural = _("product variants")
        ordering            = ["product", "is_default", "sku"]

    @property
    def is_in_stock(self) -> bool:
        if not self.track_inventory:
            return True
        return self.available_quantity > 0

    @property
    def is_low_stock(self) -> bool:
        if not self.track_inventory:
            return False
        qty = self.available_quantity
        return qty > 0 and qty <= self.low_stock_threshold

    @property
    def available_quantity(self) -> int:
        """
        Unified stock source for storefront checks.
        Prefer WarehouseStock (inventory module) when records exist; otherwise
        fall back to legacy variant stock_quantity.
        """
        try:
            from django.db.models import Sum, Count
            from apps.inventory.models import WarehouseStock

            aggregated = (
                WarehouseStock.objects
                .filter(variant_id=self.id, warehouse__is_active=True)
                .aggregate(total=Sum("available"), rows=Count("id"))
            )
            if int(aggregated.get("rows") or 0) > 0:
                return int(aggregated.get("total") or 0)
        except Exception:
            # Keep catalog resilient if inventory app/table is unavailable.
            pass
        return int(self.stock_quantity or 0)

    @property
    def discount_percentage(self) -> int | None:
        if self.compare_at_price and self.compare_at_price > self.price:
            pct = ((self.compare_at_price - self.price) / self.compare_at_price) * 100
            return round(pct)
        return None

    @property
    def has_active_offer(self) -> bool:
        return self.is_offer_live()

    def is_offer_live(self, at=None) -> bool:
        now = at or timezone.now()
        if not self.offer_is_active:
            return False
        if self.offer_price is None:
            return False
        if self.offer_price >= self.price:
            return False
        if self.offer_starts_at and now < self.offer_starts_at:
            return False
        if self.offer_ends_at and now > self.offer_ends_at:
            return False
        return True

    @property
    def effective_price(self):
        return self.offer_price if self.is_offer_live() else self.price

    @property
    def display_compare_at_price(self):
        if self.is_offer_live() and self.price > self.offer_price:
            return self.price
        if self.compare_at_price and self.compare_at_price > self.effective_price:
            return self.compare_at_price
        return None

    def clean(self):
        from django.core.exceptions import ValidationError

        errors = {}
        if self.stock_quantity < 0 and not self.allow_backorder:
            errors["stock_quantity"] = "Stock cannot be negative unless backorder is enabled."
        if self.offer_price is not None and self.offer_price >= self.price:
            errors["offer_price"] = "Offer price must be lower than regular price."
        if self.offer_starts_at and self.offer_ends_at and self.offer_ends_at <= self.offer_starts_at:
            errors["offer_ends_at"] = "Offer end must be later than offer start."
        if errors:
            raise ValidationError(errors)

    def build_name(self) -> str:
        """Build a human-readable name from attribute values."""
        values = self.attribute_values.select_related("attribute").order_by("attribute__sort_order")
        parts = [str(v.value) for v in values]
        return " / ".join(parts) if parts else self.product.name

    def __str__(self):
        return f"{self.product.name} — {self.sku}"


# ─────────────────────────────────────────────────────────────
#  Through Table: Variant ↔ AttributeValue
# ─────────────────────────────────────────────────────────────

class VariantAttributeValue(models.Model):
    """
    Explicit M2M through-table so we can enforce
    uniqueness of the full attribute combination per product.
    """

    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    variant         = models.ForeignKey(ProductVariant, on_delete=models.CASCADE)
    attribute_value = models.ForeignKey(AttributeValue,  on_delete=models.PROTECT)

    class Meta:
        unique_together = [("variant", "attribute_value")]
        verbose_name    = _("variant attribute value")

    def __str__(self):
        return f"{self.variant.sku} — {self.attribute_value}"
