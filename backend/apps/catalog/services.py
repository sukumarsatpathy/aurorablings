"""
catalog.services
~~~~~~~~~~~~~~~~
Mutation-only business logic for the catalog.

Design rules:
  - Services raise typed core.exceptions.
  - Services validate business rules (duplicate SKU, duplicate combos, etc.).
  - Views and tasks call services; services call selectors for reads.
"""

from __future__ import annotations

from django.db import transaction
from django.utils.text import slugify

from core.exceptions import ValidationError, NotFoundError, ConflictError
from core.logging import get_logger
from core.media import delete_file_if_exists, validate_image_file

from .models import (
    Category, Brand, Product, ProductMedia,
    Attribute, AttributeValue, ProductVariant, VariantAttributeValue,
    GlobalAttribute, GlobalAttributeOption, ProductAttributeConfig, ProductInfoItem, ProductStockNotifyRequest,
)
from .selectors import (
    get_product_by_id,
    get_variant_by_id,
    sku_exists,
    get_attribute_by_id,
    get_attribute_value_by_id,
)

logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────
#  Category
# ─────────────────────────────────────────────────────────────

def create_category(*, name: str, parent=None, parent_id=None, **kwargs) -> Category:
    slug = kwargs.pop("slug", None) or slugify(name)
    if parent_id and not parent:
        try:
            parent = Category.all_objects.get(id=parent_id)
        except Category.DoesNotExist:
            raise NotFoundError("Parent category not found.")

    category = Category(name=name, slug=slug, parent=parent, **kwargs)
    category.full_clean()
    category.save()
    logger.info("category_created", category_id=str(category.id), name=name)
    return category


def update_category(*, category: Category, **fields) -> Category:
    old_image_name = getattr(category.image, "name", "")
    for key, value in fields.items():
        setattr(category, key, value)
    category.full_clean()
    category.save()
    new_image_name = getattr(category.image, "name", "")
    if old_image_name and old_image_name != new_image_name:
        delete_file_if_exists(old_image_name)
    logger.info("category_updated", category_id=str(category.id))
    return category


def delete_category(*, category: Category) -> None:
    category_id = str(category.id)
    category.delete()
    logger.info("category_deleted", category_id=category_id)


# ─────────────────────────────────────────────────────────────
#  Brand
# ─────────────────────────────────────────────────────────────

def create_brand(*, name: str, **kwargs) -> Brand:
    if Brand.objects.filter(name__iexact=name).exists():
        raise ConflictError(f"Brand '{name}' already exists.")
    brand = Brand(name=name, **kwargs)
    brand.save()
    logger.info("brand_created", brand_id=str(brand.id), name=name)
    return brand


# ─────────────────────────────────────────────────────────────
#  Product
# ─────────────────────────────────────────────────────────────

@transaction.atomic
def create_product(
    *,
    name: str,
    category_id,
    brand_id=None,
    description: str = "",
    short_description: str = "",
    is_active: bool = True,
    is_featured: bool = False,
    is_digital: bool = False,
    meta_title: str = "",
    meta_description: str = "",
    rating: float = 0.0,
) -> Product:
    """
    Create a new product.
    Does NOT create variants — call create_variant() separately.
    """
    try:
        category = Category.all_objects.get(id=category_id)
    except Category.DoesNotExist:
        raise NotFoundError("Category not found.")

    brand = None
    if brand_id:
        try:
            brand = Brand.objects.get(id=brand_id)
        except Brand.DoesNotExist:
            raise NotFoundError("Brand not found.")

    product = Product(
        name=name,
        category=category,
        brand=brand,
        description=description,
        short_description=short_description,
        is_active=is_active,
        is_featured=is_featured,
        is_digital=is_digital,
        meta_title=meta_title or name,
        meta_description=meta_description or short_description,
        rating=rating,
    )
    product.save()
    logger.info("product_created", product_id=str(product.id), name=name)
    return product


@transaction.atomic
def update_product(*, product: Product, **fields) -> Product:
    protected = {"id", "slug", "created_at"}
    for key, value in fields.items():
        if key not in protected:
            setattr(product, key, value)
    product.save()
    logger.info("product_updated", product_id=str(product.id))
    return product


def deactivate_product(*, product: Product) -> Product:
    product.is_active = False
    product.save(update_fields=["is_active"])
    logger.info("product_deactivated", product_id=str(product.id))
    return product


def soft_delete_product(*, product: Product) -> None:
    product.delete()  # triggers SoftDeleteModel.delete()
    logger.info("product_soft_deleted", product_id=str(product.id))


# ─────────────────────────────────────────────────────────────
#  Product Media
# ─────────────────────────────────────────────────────────────

def add_product_media(
    *,
    product: Product,
    image,
    alt_text: str = "",
    is_primary: bool = False,
    sort_order: int = 0,
) -> ProductMedia:
    image = validate_image_file(image)
    media = ProductMedia.objects.create(
        product=product,
        image=image,
        alt_text=alt_text,
        is_primary=is_primary,
        sort_order=sort_order,
    )
    logger.info("media_added", product_id=str(product.id), media_id=str(media.id))
    return media


def delete_product_media(*, media: ProductMedia) -> None:
    media_id = str(media.id)
    delete_file_if_exists(media.image)
    media.delete()
    logger.info("media_deleted", media_id=media_id)


# ─────────────────────────────────────────────────────────────
#  Product Additional Information
# ─────────────────────────────────────────────────────────────

def create_product_info_item(
    *,
    product: Product,
    title: str,
    value: str,
    sort_order: int = 0,
    is_active: bool = True,
) -> ProductInfoItem:
    item = ProductInfoItem.objects.create(
        product=product,
        title=title.strip(),
        value=value.strip(),
        sort_order=sort_order,
        is_active=is_active,
    )
    logger.info("product_info_item_created", product_id=str(product.id), info_item_id=str(item.id))
    return item


def update_product_info_item(*, item: ProductInfoItem, **fields) -> ProductInfoItem:
    for key, value in fields.items():
        if key == "title" and isinstance(value, str):
            value = value.strip()
        if key == "value" and isinstance(value, str):
            value = value.strip()
        setattr(item, key, value)
    item.full_clean()
    item.save()
    logger.info("product_info_item_updated", info_item_id=str(item.id))
    return item


def delete_product_info_item(*, item: ProductInfoItem) -> None:
    item_id = str(item.id)
    item.delete()
    logger.info("product_info_item_deleted", info_item_id=item_id)


@transaction.atomic
def reorder_product_info_items(*, product: Product, items: list[dict]) -> None:
    id_to_order = {str(row["id"]): int(row["sort_order"]) for row in items}
    qs = ProductInfoItem.objects.filter(product=product, id__in=id_to_order.keys())
    found_ids = {str(item.id) for item in qs}
    missing = set(id_to_order.keys()) - found_ids
    if missing:
        raise NotFoundError("One or more product info items were not found.")

    for item in qs:
        item.sort_order = id_to_order[str(item.id)]
    ProductInfoItem.objects.bulk_update(qs, ["sort_order", "updated_at"])
    logger.info("product_info_items_reordered", product_id=str(product.id), count=len(found_ids))


@transaction.atomic
def create_product_stock_notify_request(
    *,
    product: Product,
    variant: ProductVariant | None = None,
    user=None,
    name: str = "",
    email: str = "",
    phone: str = "",
    quantity: int = 1,
    notes: str = "",
) -> tuple[ProductStockNotifyRequest, bool]:
    """
    Create or reuse a stock notify request for tracking customer intent.
    Returns (record, created).
    """
    normalized_email = (email or "").strip().lower()
    normalized_phone = (phone or "").strip()
    normalized_name = (name or "").strip()
    normalized_notes = (notes or "").strip()

    if user and getattr(user, "is_authenticated", False):
        if not normalized_email:
            normalized_email = (getattr(user, "email", "") or "").strip().lower()
        if not normalized_phone:
            normalized_phone = (getattr(user, "phone", "") or "").strip()
        if not normalized_name:
            normalized_name = (getattr(user, "full_name", "") or "").strip()

    if not normalized_email and not normalized_phone and not (user and getattr(user, "is_authenticated", False)):
        raise ValidationError("Email or phone is required for notify requests.")

    existing_qs = ProductStockNotifyRequest.objects.filter(product=product)
    if variant:
        existing_qs = existing_qs.filter(variant=variant)
    else:
        existing_qs = existing_qs.filter(variant__isnull=True)

    if user and getattr(user, "is_authenticated", False):
        existing_qs = existing_qs.filter(user=user)
    elif normalized_email:
        existing_qs = existing_qs.filter(email__iexact=normalized_email)
    elif normalized_phone:
        existing_qs = existing_qs.filter(phone=normalized_phone)

    existing = existing_qs.order_by("-created_at").first()
    if existing:
        updated_fields = []
        if normalized_name and existing.name != normalized_name:
            existing.name = normalized_name
            updated_fields.append("name")
        if normalized_email and existing.email != normalized_email:
            existing.email = normalized_email
            updated_fields.append("email")
        if normalized_phone and existing.phone != normalized_phone:
            existing.phone = normalized_phone
            updated_fields.append("phone")
        if quantity and existing.quantity != quantity:
            existing.quantity = quantity
            updated_fields.append("quantity")
        if normalized_notes and existing.notes != normalized_notes:
            existing.notes = normalized_notes
            updated_fields.append("notes")
        if existing.is_notified:
            existing.is_notified = False
            updated_fields.append("is_notified")
        if updated_fields:
            existing.save(update_fields=[*updated_fields, "updated_at"])
        return existing, False

    record = ProductStockNotifyRequest.objects.create(
        product=product,
        variant=variant,
        user=user if user and getattr(user, "is_authenticated", False) else None,
        name=normalized_name,
        email=normalized_email,
        phone=normalized_phone,
        quantity=max(1, int(quantity or 1)),
        notes=normalized_notes,
    )
    logger.info(
        "product_stock_notify_requested",
        product_id=str(product.id),
        variant_id=str(variant.id) if variant else None,
        record_id=str(record.id),
    )
    return record, True


# ─────────────────────────────────────────────────────────────
#  Attributes
# ─────────────────────────────────────────────────────────────

def create_attribute(*, product: Product, name: str, sort_order: int = 0) -> Attribute:
    if Attribute.objects.filter(product=product, name__iexact=name).exists():
        raise ConflictError(f"Attribute '{name}' already exists for this product.")
    attr = Attribute.objects.create(product=product, name=name, sort_order=sort_order)
    logger.info("attribute_created", product_id=str(product.id), attribute=name)
    return attr


def create_attribute_value(
    *, attribute: Attribute, value: str, sort_order: int = 0
) -> AttributeValue:
    if AttributeValue.objects.filter(attribute=attribute, value__iexact=value).exists():
        raise ConflictError(f"Value '{value}' already exists for attribute '{attribute.name}'.")
    av = AttributeValue.objects.create(attribute=attribute, value=value, sort_order=sort_order)
    logger.info("attribute_value_created", attribute_id=str(attribute.id), value=value)
    return av


@transaction.atomic
def create_global_attribute(
    *,
    name: str,
    options: list[str] | None = None,
    sort_order: int = 0,
    is_active: bool = True,
) -> GlobalAttribute:
    if GlobalAttribute.objects.filter(name__iexact=name).exists():
        raise ConflictError(f"Global attribute '{name}' already exists.")

    attribute = GlobalAttribute.objects.create(
        name=name.strip(),
        sort_order=sort_order,
        is_active=is_active,
    )
    _sync_global_options(attribute, options or [])
    logger.info("global_attribute_created", attribute_id=str(attribute.id), name=attribute.name)
    return attribute


@transaction.atomic
def update_global_attribute(
    *,
    attribute: GlobalAttribute,
    name: str | None = None,
    options: list[str] | None = None,
    sort_order: int | None = None,
    is_active: bool | None = None,
) -> GlobalAttribute:
    if name is not None:
        normalized = name.strip()
        if (
            GlobalAttribute.objects
            .exclude(id=attribute.id)
            .filter(name__iexact=normalized)
            .exists()
        ):
            raise ConflictError(f"Global attribute '{normalized}' already exists.")
        attribute.name = normalized
    if sort_order is not None:
        attribute.sort_order = sort_order
    if is_active is not None:
        attribute.is_active = is_active
    attribute.full_clean()
    attribute.save()

    if options is not None:
        _sync_global_options(attribute, options)
        _sync_linked_products_legacy_attribute(attribute)

    logger.info("global_attribute_updated", attribute_id=str(attribute.id))
    return attribute


@transaction.atomic
def delete_global_attribute(*, attribute: GlobalAttribute) -> None:
    """
    Remove the global attribute and unlink from products.
    Also remove mirrored legacy product attributes for linked products.
    """
    linked_product_ids = list(
        ProductAttributeConfig.objects.filter(global_attribute=attribute).values_list("product_id", flat=True)
    )
    legacy_attrs = Attribute.objects.filter(product_id__in=linked_product_ids, name__iexact=attribute.name)
    for legacy in legacy_attrs:
        legacy.delete()
    attribute.delete()
    logger.info("global_attribute_deleted", attribute_id=str(attribute.id))


@transaction.atomic
def assign_global_attribute_to_product(
    *,
    product: Product,
    global_attribute: GlobalAttribute,
    sort_order: int = 0,
) -> ProductAttributeConfig:
    config, _ = ProductAttributeConfig.objects.get_or_create(
        product=product,
        global_attribute=global_attribute,
        defaults={"sort_order": sort_order, "is_active": True},
    )
    if not config.is_active:
        config.is_active = True
        config.save(update_fields=["is_active", "updated_at"])
    _ensure_legacy_attribute_for_product(product, global_attribute)
    logger.info(
        "product_global_attribute_assigned",
        product_id=str(product.id),
        global_attribute_id=str(global_attribute.id),
    )
    return config


@transaction.atomic
def unassign_global_attribute_from_product(
    *,
    product: Product,
    global_attribute: GlobalAttribute,
) -> None:
    ProductAttributeConfig.objects.filter(
        product=product,
        global_attribute=global_attribute,
    ).delete()
    Attribute.objects.filter(product=product, name__iexact=global_attribute.name).delete()
    logger.info(
        "product_global_attribute_unassigned",
        product_id=str(product.id),
        global_attribute_id=str(global_attribute.id),
    )


# ─────────────────────────────────────────────────────────────
#  Variants
# ─────────────────────────────────────────────────────────────

@transaction.atomic
def create_variant(
    *,
    product: Product,
    sku: str,
    price: float | str,
    attribute_value_ids: list,
    compare_at_price=None,
    offer_price=None,
    offer_starts_at=None,
    offer_ends_at=None,
    offer_label: str = "",
    offer_is_active: bool = False,
    cost_price=None,
    stock_quantity: int = 0,
    is_default: bool = False,
    weight_grams: int | None = None,
    name: str = "",
) -> ProductVariant:
    """
    Create a product variant.

    Validates:
      - SKU uniqueness across the entire catalog
      - No duplicate attribute combination for the same product
      - Pricing mandatory (price > 0)
    """
    # ── SKU uniqueness ─────────────────────────────────────────
    if sku_exists(sku):
        raise ConflictError(f"SKU '{sku}' is already in use.")

    price = _coerce_decimal(price, "price")
    if compare_at_price is not None:
        compare_at_price = _coerce_decimal(compare_at_price, "compare_at_price")
    if offer_price is not None:
        offer_price = _coerce_decimal(offer_price, "offer_price")
    if cost_price is not None:
        cost_price = _coerce_decimal(cost_price, "cost_price")
    _validate_offer_fields(
        price=price,
        offer_price=offer_price,
        offer_starts_at=offer_starts_at,
        offer_ends_at=offer_ends_at,
    )

    # ── Attribute values exist and belong to this product ──────
    av_objects = _resolve_attribute_values(product, attribute_value_ids)

    # ── Duplicate combination guard ────────────────────────────
    _assert_no_duplicate_combination(product, av_objects, exclude_variant=None)

    # ── If this is default, clear existing default ─────────────
    if is_default:
        ProductVariant.objects.filter(product=product, is_default=True).update(is_default=False)

    variant = ProductVariant.objects.create(
        product=product,
        sku=sku,
        price=price,
        compare_at_price=compare_at_price,
        offer_price=offer_price,
        offer_starts_at=offer_starts_at,
        offer_ends_at=offer_ends_at,
        offer_label=offer_label,
        offer_is_active=offer_is_active,
        cost_price=cost_price,
        stock_quantity=stock_quantity,
        is_default=is_default,
        weight_grams=weight_grams,
    )

    # ── Attach attribute values via through table ──────────────
    VariantAttributeValue.objects.bulk_create([
        VariantAttributeValue(variant=variant, attribute_value=av)
        for av in av_objects
    ])

    # ── Auto-build name if not provided ──────────────────────-
    if not name:
        name = variant.build_name()
    variant.name = name
    variant.save(update_fields=["name"])

    logger.info(
        "variant_created",
        product_id=str(product.id),
        variant_id=str(variant.id),
        sku=sku,
    )
    return variant


@transaction.atomic
def update_variant(
    *,
    variant: ProductVariant,
    sku: str | None = None,
    price=None,
    compare_at_price=None,
    offer_price=None,
    offer_starts_at=None,
    offer_ends_at=None,
    offer_label=None,
    offer_is_active: bool | None = None,
    stock_quantity: int | None = None,
    is_default: bool | None = None,
    attribute_value_ids: list | None = None,
    **fields,
) -> ProductVariant:
    """
    Update an existing variant.
    Attribute combination is re-validated if attribute_value_ids is provided.
    """
    if sku and sku != variant.sku:
        if sku_exists(sku):
            raise ConflictError(f"SKU '{sku}' is already in use.")
        variant.sku = sku

    if price is not None:
        variant.price = _coerce_decimal(price, "price")
    if compare_at_price is not None:
        variant.compare_at_price = _coerce_decimal(compare_at_price, "compare_at_price")
    if offer_price is not None:
        variant.offer_price = _coerce_decimal(offer_price, "offer_price")
    if offer_starts_at is not None:
        variant.offer_starts_at = offer_starts_at
    if offer_ends_at is not None:
        variant.offer_ends_at = offer_ends_at
    if offer_label is not None:
        variant.offer_label = offer_label
    if offer_is_active is not None:
        variant.offer_is_active = offer_is_active
    if stock_quantity is not None:
        variant.stock_quantity = stock_quantity

    if is_default is True:
        ProductVariant.objects.filter(
            product=variant.product, is_default=True
        ).exclude(pk=variant.pk).update(is_default=False)
        variant.is_default = True

    if attribute_value_ids is not None:
        av_objects = _resolve_attribute_values(variant.product, attribute_value_ids)
        _assert_no_duplicate_combination(variant.product, av_objects, exclude_variant=variant)

        # Re-link attribute values
        VariantAttributeValue.objects.filter(variant=variant).delete()
        VariantAttributeValue.objects.bulk_create([
            VariantAttributeValue(variant=variant, attribute_value=av)
            for av in av_objects
        ])
        variant.name = variant.build_name()

    # Extra fields
    for key, value in fields.items():
        setattr(variant, key, value)

    _validate_offer_fields(
        price=variant.price,
        offer_price=variant.offer_price,
        offer_starts_at=variant.offer_starts_at,
        offer_ends_at=variant.offer_ends_at,
    )

    variant.save()
    logger.info("variant_updated", variant_id=str(variant.id), sku=variant.sku)
    return variant


def delete_variant(*, variant: ProductVariant) -> None:
    """
    Hard-delete a variant. Ensures the product won't be left with zero variants.
    """
    remaining = ProductVariant.objects.filter(product=variant.product).exclude(pk=variant.pk).count()
    if remaining == 0:
        raise ValidationError("Cannot delete the last variant of a product.")
    variant_id = str(variant.id)
    variant.delete()
    logger.info("variant_deleted", variant_id=variant_id)


# ─────────────────────────────────────────────────────────────
#  Private helpers
# ─────────────────────────────────────────────────────────────

def _coerce_decimal(value, field_name: str):
    from decimal import Decimal, InvalidOperation
    try:
        d = Decimal(str(value))
        if d < 0:
            raise ValidationError(f"{field_name} must be non-negative.")
        return d
    except InvalidOperation:
        raise ValidationError(f"{field_name} must be a valid decimal number.")


def _resolve_attribute_values(product: Product, ids: list) -> list:
    """Return AttributeValue objects, verifying they belong to this product."""
    if not ids:
        return []

    avs = list(
        AttributeValue.objects.select_related("attribute").filter(id__in=ids)
    )
    found_ids = {str(av.id) for av in avs}
    for id_ in ids:
        if str(id_) not in found_ids:
            raise NotFoundError(f"AttributeValue {id_} not found.")

    for av in avs:
        if av.attribute.product_id != product.id:
            raise ValidationError(
                f"AttributeValue '{av.value}' does not belong to product '{product.name}'."
            )

    # One value per attribute dimension
    attr_seen = {}
    for av in avs:
        attr_id = str(av.attribute_id)
        if attr_id in attr_seen:
            raise ValidationError(
                f"Cannot specify two values for the same attribute '{av.attribute.name}'."
            )
        attr_seen[attr_id] = True

    return avs


def _assert_no_duplicate_combination(
    product: Product,
    av_objects: list,
    exclude_variant,
) -> None:
    """
    Ensure no existing variant has the exact same attribute value set.
    """
    if not av_objects:
        return

    av_ids = frozenset(str(av.id) for av in av_objects)

    qs = ProductVariant.objects.filter(product=product)
    if exclude_variant:
        qs = qs.exclude(pk=exclude_variant.pk)

    for existing_variant in qs.prefetch_related("attribute_values"):
        existing_ids = frozenset(
            str(av.id) for av in existing_variant.attribute_values.all()
        )
        if existing_ids == av_ids:
            raise ConflictError(
                f"A variant with this attribute combination already exists (SKU: {existing_variant.sku})."
            )


def _validate_offer_fields(*, price, offer_price, offer_starts_at, offer_ends_at) -> None:
    if offer_price is not None and offer_price >= price:
        raise ValidationError("Offer price must be lower than regular price.")
    if offer_starts_at and offer_ends_at and offer_ends_at <= offer_starts_at:
        raise ValidationError("Offer end must be later than offer start.")


def _sanitize_options(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen = set()
    for raw in values:
        value = (raw or "").strip()
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(value)
    return cleaned


def _sync_global_options(attribute: GlobalAttribute, options: list[str]) -> None:
    """
    Replace active option set using soft-deactivation for removed options.
    """
    cleaned = _sanitize_options(options)
    existing = {
        opt.value.lower(): opt
        for opt in GlobalAttributeOption.objects.filter(global_attribute=attribute)
    }
    active_keys = set()

    for idx, value in enumerate(cleaned):
        key = value.lower()
        active_keys.add(key)
        if key in existing:
            option = existing[key]
            option.value = value
            option.sort_order = idx
            option.is_active = True
            option.save(update_fields=["value", "sort_order", "is_active", "updated_at"])
        else:
            GlobalAttributeOption.objects.create(
                global_attribute=attribute,
                value=value,
                sort_order=idx,
                is_active=True,
            )

    for key, option in existing.items():
        if key not in active_keys and option.is_active:
            option.is_active = False
            option.save(update_fields=["is_active", "updated_at"])


def _ensure_legacy_attribute_for_product(product: Product, global_attribute: GlobalAttribute) -> Attribute:
    legacy_attr, _ = Attribute.objects.get_or_create(
        product=product,
        name=global_attribute.name,
        defaults={"sort_order": global_attribute.sort_order},
    )
    if legacy_attr.sort_order != global_attribute.sort_order:
        legacy_attr.sort_order = global_attribute.sort_order
        legacy_attr.save(update_fields=["sort_order", "updated_at"])

    active_options = list(
        GlobalAttributeOption.objects.filter(
            global_attribute=global_attribute,
            is_active=True,
        ).order_by("sort_order", "value")
    )
    existing_values = {
        val.value.lower(): val
        for val in AttributeValue.objects.filter(attribute=legacy_attr)
    }
    for idx, option in enumerate(active_options):
        key = option.value.lower()
        current = existing_values.get(key)
        if current:
            if current.sort_order != idx:
                current.sort_order = idx
                current.save(update_fields=["sort_order", "updated_at"])
        else:
            AttributeValue.objects.create(
                attribute=legacy_attr,
                value=option.value,
                sort_order=idx,
            )
    return legacy_attr


def _sync_linked_products_legacy_attribute(attribute: GlobalAttribute) -> None:
    linked_products = Product.objects.filter(
        global_attribute_configs__global_attribute=attribute,
    ).distinct()
    for product in linked_products:
        _ensure_legacy_attribute_for_product(product, attribute)
