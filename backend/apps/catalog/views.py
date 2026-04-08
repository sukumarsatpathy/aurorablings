"""
catalog.views
~~~~~~~~~~~~~
Thin viewsets — validate → service → respond.

Public endpoints (list, detail) are open.
Write endpoints require IsAuthenticated + IsStaffOrAdmin.
"""
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import AllowAny, IsAuthenticated

from apps.accounts.permissions import IsStaffOrAdmin
from core.response import success_response, error_response
from core.viewsets import BaseViewSet, ReadOnlyViewSet, FullCRUDViewSet
from core.exceptions import NotFoundError
from core.logging import get_logger
from audit.models import ActorType, AuditAction
from audit.services.activity_logger import log_activity

from . import services, selectors
from .filters import ProductFilter
from .models import (
    Category, Brand, Product, ProductVariant,
    Attribute, AttributeValue, ProductMedia, GlobalAttribute, ProductInfoItem,
)
from .serializers import (
    CategorySerializer, CategoryTreeSerializer,
    BrandSerializer,
    ProductListSerializer, ProductDetailSerializer, ProductWriteSerializer,
    ProductVariantSerializer, ProductVariantWriteSerializer,
    AttributeSerializer, AttributeValueSerializer,
    ProductAttributeWriteSerializer,
    AttributeAdminSerializer, AttributeAdminWriteSerializer,
    ProductMediaSerializer, DealProductSerializer,
    ProductInfoItemSerializer, ProductInfoItemWriteSerializer, ProductInfoItemReorderSerializer,
    ProductStockNotifyRequestSerializer, ProductStockNotifyRequestWriteSerializer,
)

logger = get_logger(__name__)


def _is_catalog_staff(user) -> bool:
    return bool(
        user
        and getattr(user, "is_authenticated", False)
        and getattr(user, "role", "") in {"admin", "staff"}
    )


# ─────────────────────────────────────────────────────────────
#  Category
# ─────────────────────────────────────────────────────────────

class CategoryViewSet(BaseViewSet):
    """
    GET    /categories/         → flat list
    GET    /categories/tree/    → nested tree
    GET    /categories/{id}/    → detail
    POST   /categories/         → create         [staff+]
    PATCH  /categories/{id}/    → partial update [staff+]
    DELETE /categories/{id}/    → destroy        [staff+]
    """
    queryset = Category.all_objects.all()
    parser_classes = [MultiPartParser, FormParser]

    def get_permissions(self):
        if self.action in ("list", "retrieve", "tree"):
            return [AllowAny()]
        return [IsAuthenticated(), IsStaffOrAdmin()]

    def list(self, request):
        latest = str(request.query_params.get("latest", "")).strip().lower() in {"1", "true", "yes", "on"}
        qs = selectors.get_all_categories(
            active_only=not _is_catalog_staff(request.user),
            latest_first=latest,
        )
        return self.paginate(qs, CategorySerializer)

    def retrieve(self, request, pk=None):
        cat = selectors.get_category_by_id(pk)
        if not cat:
            raise NotFoundError("Category not found.")
        return self.ok(data=CategorySerializer(cat).data)

    @action(detail=False, methods=["get"])
    def tree(self, request):
        roots = selectors.get_all_categories().filter(parent__isnull=True)
        return self.ok(data=CategoryTreeSerializer(roots, many=True).data)

    def create(self, request):
        s = CategorySerializer(data=request.data)
        s.is_valid(raise_exception=True)
        category = services.create_category(**s.validated_data)
        return self.created(data=CategorySerializer(category).data)

    def partial_update(self, request, pk=None):
        category = selectors.get_category_by_id(pk)
        if not category:
            raise NotFoundError("Category not found.")
        s = CategorySerializer(data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        category = services.update_category(category=category, **s.validated_data)
        return self.ok(data=CategorySerializer(category).data)

    def destroy(self, request, pk=None):
        category = selectors.get_category_by_id(pk)
        if not category:
            raise NotFoundError("Category not found.")
        services.delete_category(category=category)
        return self.ok(message="Category deleted.")


# ─────────────────────────────────────────────────────────────
#  Brand
# ─────────────────────────────────────────────────────────────

class BrandViewSet(BaseViewSet):
    queryset = Brand.objects.all()

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [AllowAny()]
        return [IsAuthenticated(), IsStaffOrAdmin()]

    def list(self, request):
        qs = selectors.get_all_brands()
        return self.paginate(qs, BrandSerializer)

    def retrieve(self, request, pk=None):
        brand = selectors.get_brand_by_id(pk)
        if not brand:
            raise NotFoundError("Brand not found.")
        return self.ok(data=BrandSerializer(brand).data)

    def create(self, request):
        s = BrandSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        brand = services.create_brand(**s.validated_data)
        return self.created(data=BrandSerializer(brand).data)


# ─────────────────────────────────────────────────────────────
#  Product
# ─────────────────────────────────────────────────────────────

class ProductViewSet(BaseViewSet):
    """
    GET    /products/           → paginated list (public, filtered)
    GET    /products/{id}/      → full detail   (public)
    GET    /products/slug/{slug}/ → by slug     (public)
    POST   /products/           → create        [staff+]
    PATCH  /products/{id}/      → update        [staff+]
    DELETE /products/{id}/      → soft delete   [staff+]
    GET    /products/{id}/variants/   → variant list
    POST   /products/{id}/variants/   → add variant
    POST   /products/{id}/media/      → upload image
    """

    queryset = Product.all_objects.all()
    filter_backends  = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class  = ProductFilter
    search_fields    = ["name", "description", "variants__sku"]
    ordering_fields  = ["created_at", "name"]
    ordering         = ["-created_at"]

    def get_permissions(self):
        if self.action in ("list", "retrieve", "by_slug", "variants", "deals", "info_items", "notify_me"):
            return [AllowAny()]
        return [IsAuthenticated(), IsStaffOrAdmin()]

    # ── List ──────────────────────────────────────────────────
    def list(self, request):
        qs = selectors.get_product_list(published_only=not _is_catalog_staff(request.user))
        qs = self.filter_queryset(qs)
        return self.paginate(qs, ProductListSerializer)

    @action(detail=False, methods=["get"])
    def deals(self, request):
        """
        GET /products/deals/ -> returns products with active offers.
        """
        qs = selectors.get_deal_products(limit=10)
        # Use DealProductSerializer which includes variant offer data for the countdown timer
        serializer = DealProductSerializer(qs, many=True, context={"request": request})
        return self.ok(data=serializer.data)

    # ── Detail ────────────────────────────────────────────────
    def retrieve(self, request, pk=None):
        product = selectors.get_product_by_id(pk)
        if not product:
            raise NotFoundError("Product not found.")
        return self.ok(data=ProductDetailSerializer(product, context={"request": request}).data)

    @action(detail=False, methods=["get"], url_path="slug/(?P<slug>[^/.]+)")
    def by_slug(self, request, slug=None):
        product = selectors.get_product_by_slug(slug)
        if not product:
            raise NotFoundError("Product not found.")
        return self.ok(data=ProductDetailSerializer(product, context={"request": request}).data)

    # ── Create ────────────────────────────────────────────────
    def create(self, request):
        s = ProductWriteSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        product = services.create_product(**s.validated_data)
        log_activity(
            user=request.user,
            actor_type=ActorType.ADMIN if request.user.role == "admin" else ActorType.STAFF,
            action=AuditAction.CREATE,
            entity_type="product",
            entity_id=str(product.id),
            description=f"Created product '{product.name}'",
            metadata={
                "name": product.name,
                "category_id": str(product.category_id),
                "brand_id": str(product.brand_id) if product.brand_id else None,
            },
            request=request,
        )
        return self.created(data=ProductDetailSerializer(product, context={"request": request}).data)

    # ── Update ────────────────────────────────────────────────
    def partial_update(self, request, pk=None):
        product = selectors.get_product_by_id(pk, published_only=False)
        if not product:
            raise NotFoundError("Product not found.")
        old_values = {
            "name": product.name,
            "description": product.description,
            "short_description": product.short_description,
            "is_active": product.is_active,
            "is_featured": product.is_featured,
            "meta_title": product.meta_title,
            "meta_description": product.meta_description,
        }
        s = ProductWriteSerializer(data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        product = services.update_product(product=product, **s.validated_data)
        new_values = {
            "name": product.name,
            "description": product.description,
            "short_description": product.short_description,
            "is_active": product.is_active,
            "is_featured": product.is_featured,
            "meta_title": product.meta_title,
            "meta_description": product.meta_description,
        }
        log_activity(
            user=request.user,
            actor_type=ActorType.ADMIN if request.user.role == "admin" else ActorType.STAFF,
            action=AuditAction.UPDATE,
            entity_type="product",
            entity_id=str(product.id),
            description=f"Updated product '{product.name}'",
            metadata={"old_value": old_values, "new_value": new_values},
            request=request,
        )
        return self.ok(data=ProductDetailSerializer(product, context={"request": request}).data)

    # ── Soft Delete ───────────────────────────────────────────
    def destroy(self, request, pk=None):
        product = selectors.get_product_by_id(pk, published_only=False)
        if not product:
            raise NotFoundError("Product not found.")
        product_name = product.name
        services.soft_delete_product(product=product)
        log_activity(
            user=request.user,
            actor_type=ActorType.ADMIN if request.user.role == "admin" else ActorType.STAFF,
            action=AuditAction.DELETE,
            entity_type="product",
            entity_id=str(product.id),
            description=f"Deleted product '{product_name}'",
            metadata={"name": product_name},
            request=request,
        )
        return self.ok(message="Product deleted.")

    # ── Variants sub-resource ─────────────────────────────────
    @action(detail=True, methods=["get", "post"], url_path="variants")
    def variants(self, request, pk=None):
        product = selectors.get_product_by_id(pk, published_only=False)
        if not product:
            raise NotFoundError("Product not found.")

        if request.method == "GET":
            qs = selectors.get_variants_for_product(product)
            return self.ok(data=ProductVariantSerializer(qs, many=True).data)

        # POST — staff only
        if not (request.user.is_authenticated and request.user.role in ("admin", "staff")):
            return error_response(message="Permission denied.", error_code="forbidden", status_code=403)

        s = ProductVariantWriteSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        variant = services.create_variant(product=product, **s.validated_data)
        return self.created(data=ProductVariantSerializer(variant).data)

    # ── Media upload ──────────────────────────────────────────
    @action(
        detail=True,
        methods=["post"],
        url_path="media",
        parser_classes=[MultiPartParser, FormParser],
        permission_classes=[IsAuthenticated, IsStaffOrAdmin],
    )
    def media(self, request, pk=None):
        product = selectors.get_product_by_id(pk, published_only=False)
        if not product:
            raise NotFoundError("Product not found.")

        image      = request.FILES.get("image")
        alt_text   = request.data.get("alt_text", "")
        is_primary = request.data.get("is_primary", "false").lower() == "true"
        sort_order = int(request.data.get("sort_order", 0))

        if not image:
            return self.bad_request(message="No image file provided.")

        media = services.add_product_media(
            product=product,
            image=image,
            alt_text=alt_text,
            is_primary=is_primary,
            sort_order=sort_order,
        )
        return self.created(data=ProductMediaSerializer(media).data)

    @action(
        detail=True,
        methods=["patch", "delete"],
        url_path=r"media/(?P<media_id>[^/.]+)",
        permission_classes=[IsAuthenticated, IsStaffOrAdmin],
    )
    def media_detail(self, request, pk=None, media_id=None):
        product = selectors.get_product_by_id(pk, published_only=False)
        if not product:
            raise NotFoundError("Product not found.")

        try:
            media = ProductMedia.objects.get(id=media_id, product=product)
        except ProductMedia.DoesNotExist:
            raise NotFoundError("Product media not found.")

        if request.method == "DELETE":
            services.delete_product_media(media=media)
            return self.ok(message="Product media deleted.")

        # PATCH
        if "alt_text" in request.data:
            media.alt_text = request.data.get("alt_text", "")
        if "sort_order" in request.data:
            media.sort_order = int(request.data.get("sort_order") or 0)
        if "is_primary" in request.data:
            raw = request.data.get("is_primary")
            if isinstance(raw, bool):
                media.is_primary = raw
            else:
                media.is_primary = str(raw).lower() == "true"
        media.save()
        return self.ok(data=ProductMediaSerializer(media).data, message="Product media updated.")

    @action(
        detail=True,
        methods=["get", "post"],
        url_path="attributes",
    )
    def attributes(self, request, pk=None):
        product = selectors.get_product_by_id(pk, published_only=False)
        if not product:
            raise NotFoundError("Product not found.")

        if request.method == "GET":
            qs = selectors.get_attributes_for_product(product)
            return self.ok(data=AttributeSerializer(qs, many=True).data)

        if not (request.user.is_authenticated and request.user.role in ("admin", "staff")):
            return error_response(message="Permission denied.", error_code="forbidden", status_code=403)

        s = ProductAttributeWriteSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        global_attribute = None
        global_attribute_id = s.validated_data.get("global_attribute_id")
        options = s.validated_data.get("options", [])

        if global_attribute_id:
            global_attribute = selectors.get_global_attribute_by_id(global_attribute_id)
            if not global_attribute:
                raise NotFoundError("Global attribute not found.")
            if options:
                global_attribute = services.update_global_attribute(
                    attribute=global_attribute,
                    options=options,
                )
        else:
            name = (s.validated_data.get("name") or "").strip()
            if not name:
                return self.bad_request(message="Attribute name is required.")
            global_attribute = GlobalAttribute.objects.filter(name__iexact=name).first()
            if global_attribute:
                if options:
                    global_attribute = services.update_global_attribute(
                        attribute=global_attribute,
                        options=options,
                    )
            else:
                global_attribute = services.create_global_attribute(
                    name=name,
                    options=options,
                    sort_order=0,
                )

        services.assign_global_attribute_to_product(
            product=product,
            global_attribute=global_attribute,
            sort_order=0,
        )

        legacy = (
            Attribute.objects
            .filter(product=product, name__iexact=global_attribute.name)
            .prefetch_related("values")
            .first()
        )
        if not legacy:
            raise NotFoundError("Attribute mapping could not be created.")
        return self.created(data=AttributeSerializer(legacy).data)

    @action(
        detail=True,
        methods=["patch", "delete"],
        url_path=r"attributes/(?P<attribute_id>[^/.]+)",
        permission_classes=[IsAuthenticated, IsStaffOrAdmin],
    )
    def attribute_detail(self, request, pk=None, attribute_id=None):
        product = selectors.get_product_by_id(pk, published_only=False)
        if not product:
            raise NotFoundError("Product not found.")

        try:
            attribute = Attribute.objects.get(id=attribute_id, product=product)
        except Attribute.DoesNotExist:
            raise NotFoundError("Attribute not found.")

        if request.method == "DELETE":
            global_attribute = GlobalAttribute.objects.filter(name__iexact=attribute.name).first()
            if global_attribute:
                services.unassign_global_attribute_from_product(
                    product=product,
                    global_attribute=global_attribute,
                )
            else:
                attribute.delete()
            return self.ok(message="Attribute deleted.")

        s = ProductAttributeWriteSerializer(data=request.data, partial=True)
        s.is_valid(raise_exception=True)

        global_attribute = GlobalAttribute.objects.filter(name__iexact=attribute.name).first()
        if global_attribute:
            new_name = s.validated_data.get("name")
            if isinstance(new_name, str):
                new_name = new_name.strip() or None
            global_attribute = services.update_global_attribute(
                attribute=global_attribute,
                name=new_name,
                options=s.validated_data.get("options") if "options" in s.validated_data else None,
            )
            services.assign_global_attribute_to_product(
                product=product,
                global_attribute=global_attribute,
                sort_order=attribute.sort_order,
            )
            updated = (
                Attribute.objects
                .filter(product=product, name__iexact=global_attribute.name)
                .prefetch_related("values")
                .first()
            )
            return self.ok(data=AttributeSerializer(updated).data, message="Attribute updated.")

        if "name" in s.validated_data:
            attribute.name = s.validated_data["name"].strip()
            attribute.full_clean()
            attribute.save(update_fields=["name", "updated_at"])

        if "options" in s.validated_data:
            AttributeValue.objects.filter(attribute=attribute).delete()
            options = []
            seen = set()
            for raw in s.validated_data.get("options", []):
                value = raw.strip()
                if not value:
                    continue
                norm = value.lower()
                if norm in seen:
                    continue
                seen.add(norm)
                options.append(value)
            for idx, value in enumerate(options):
                services.create_attribute_value(attribute=attribute, value=value, sort_order=idx)

        attribute = selectors.get_attribute_by_id(attribute.id)
        return self.ok(data=AttributeSerializer(attribute).data, message="Attribute updated.")

    @action(
        detail=True,
        methods=["get", "post"],
        url_path="info-items",
    )
    def info_items(self, request, pk=None):
        product = selectors.get_product_by_id(pk, published_only=False)
        if not product:
            raise NotFoundError("Product not found.")

        if request.method == "GET":
            qs = selectors.get_info_items_for_product(product, active_only=not _is_catalog_staff(request.user))
            return self.ok(data=ProductInfoItemSerializer(qs, many=True).data)

        if not (request.user.is_authenticated and request.user.role in ("admin", "staff")):
            return error_response(message="Permission denied.", error_code="forbidden", status_code=403)

        serializer = ProductInfoItemWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = services.create_product_info_item(
            product=product,
            **serializer.validated_data,
        )
        return self.created(data=ProductInfoItemSerializer(item).data)

    @action(
        detail=True,
        methods=["patch", "delete"],
        url_path=r"info-items/(?P<item_id>[0-9a-fA-F-]{36})",
        permission_classes=[IsAuthenticated, IsStaffOrAdmin],
    )
    def info_item_detail(self, request, pk=None, item_id=None):
        product = selectors.get_product_by_id(pk, published_only=False)
        if not product:
            raise NotFoundError("Product not found.")
        try:
            item = ProductInfoItem.objects.get(id=item_id, product=product)
        except ProductInfoItem.DoesNotExist:
            raise NotFoundError("Product info item not found.")

        if request.method == "DELETE":
            services.delete_product_info_item(item=item)
            return self.ok(message="Product info item deleted.")

        serializer = ProductInfoItemWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated = services.update_product_info_item(item=item, **serializer.validated_data)
        return self.ok(data=ProductInfoItemSerializer(updated).data, message="Product info item updated.")

    @action(
        detail=True,
        methods=["post"],
        url_path="info-items/reorder",
        permission_classes=[IsAuthenticated, IsStaffOrAdmin],
    )
    def info_items_reorder(self, request, pk=None):
        product = selectors.get_product_by_id(pk, published_only=False)
        if not product:
            raise NotFoundError("Product not found.")

        serializer = ProductInfoItemReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.reorder_product_info_items(product=product, items=serializer.validated_data["items"])
        return self.ok(message="Product info items reordered.")

    @action(
        detail=True,
        methods=["post"],
        url_path="notify-me",
        permission_classes=[AllowAny],
    )
    def notify_me(self, request, pk=None):
        product = selectors.get_product_by_id(pk, published_only=not _is_catalog_staff(request.user))
        if not product:
            raise NotFoundError("Product not found.")

        serializer = ProductStockNotifyRequestWriteSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        variant = None
        variant_id = serializer.validated_data.get("variant_id")
        if variant_id:
            variant = selectors.get_variant_by_id(variant_id)
            if not variant or str(variant.product_id) != str(product.id):
                raise NotFoundError("Variant not found for this product.")

        record, created = services.create_product_stock_notify_request(
            product=product,
            variant=variant,
            user=request.user if request.user.is_authenticated else None,
            name=serializer.validated_data.get("name", ""),
            email=serializer.validated_data.get("email", ""),
            phone=serializer.validated_data.get("phone", ""),
            quantity=serializer.validated_data.get("quantity", 1),
            notes=serializer.validated_data.get("notes", ""),
        )

        if created:
            try:
                from apps.notifications.tasks import trigger_event_task
                from apps.notifications.events import NotificationEvent

                recipient_email = record.email or (record.user.email if record.user_id and record.user else "")
                if recipient_email:
                    media = product.media.filter(is_primary=True).first() or product.media.first()
                    product_image_url = ""
                    if media and getattr(media, "image", None):
                        image_url = str(media.image.url or "")
                        from django.conf import settings

                        backend_url = str(getattr(settings, "BACKEND_URL", "") or "").rstrip("/")
                        product_image_url = image_url if image_url.startswith("http") else f"{backend_url}{image_url}" if backend_url else image_url

                    customer_name = (
                        record.name
                        or (record.user.get_full_name() if record.user_id and record.user else "")
                        or "Customer"
                    )
                    trigger_event_task.delay(
                        event=NotificationEvent.PRODUCT_NOTIFY_ME,
                        context={
                            "product_name": product.name,
                            "product": {
                                "name": product.name,
                                "image_url": product_image_url,
                                "price": str(getattr(variant, "offer_price", "") or getattr(variant, "price", "") or ""),
                            },
                            "product_url": f"/products/{product.slug}/",
                            "customer_name": customer_name,
                            "user_name": customer_name,
                        },
                        user_id=str(record.user_id) if record.user_id else None,
                        recipient_email=recipient_email,
                    )
            except Exception:
                logger.exception("notify_me_email_queue_failed", product_id=str(product.id), notify_request_id=str(record.id))

        payload = ProductStockNotifyRequestSerializer(record).data
        if created:
            return self.created(data=payload, message="Notify request submitted.")
        return self.ok(data=payload, message="Notify request already exists and was updated.")


# ─────────────────────────────────────────────────────────────
#  Variant (direct access)
# ─────────────────────────────────────────────────────────────

class ProductVariantViewSet(BaseViewSet):
    """
    PATCH  /variants/{id}/    → update variant [staff+]
    DELETE /variants/{id}/    → delete variant [staff+]
    """
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]
    queryset = ProductVariant.objects.all()

    def retrieve(self, request, pk=None):
        variant = selectors.get_variant_by_id(pk)
        if not variant:
            raise NotFoundError("Variant not found.")
        return self.ok(data=ProductVariantSerializer(variant).data)

    def partial_update(self, request, pk=None):
        variant = selectors.get_variant_by_id(pk)
        if not variant:
            raise NotFoundError("Variant not found.")
        old_price = variant.price
        old_offer_price = variant.offer_price
        old_stock = variant.stock_quantity
        s = ProductVariantWriteSerializer(data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        variant = services.update_variant(variant=variant, **s.validated_data)
        if old_price != variant.price or old_offer_price != variant.offer_price:
            log_activity(
                user=request.user,
                actor_type=ActorType.ADMIN if request.user.role == "admin" else ActorType.STAFF,
                action=AuditAction.UPDATE,
                entity_type="product_price",
                entity_id=str(variant.id),
                description=f"Updated price for SKU {variant.sku}",
                metadata={
                    "sku": variant.sku,
                    "old_price": old_price,
                    "new_price": variant.price,
                    "old_offer_price": old_offer_price,
                    "new_offer_price": variant.offer_price,
                },
                request=request,
            )
        if old_stock != variant.stock_quantity:
            log_activity(
                user=request.user,
                actor_type=ActorType.ADMIN if request.user.role == "admin" else ActorType.STAFF,
                action=AuditAction.UPDATE,
                entity_type="inventory",
                entity_id=str(variant.id),
                description=f"Updated stock for SKU {variant.sku}",
                metadata={"sku": variant.sku, "old_stock": old_stock, "new_stock": variant.stock_quantity},
                request=request,
            )
            if old_stock <= 0 < variant.stock_quantity:
                try:
                    from apps.notifications.tasks import notify_back_in_stock_task
                    notify_back_in_stock_task.delay(str(variant.product_id))
                except Exception:
                    logger.exception("failed_to_queue_back_in_stock_notification", product_id=str(variant.product_id))
        return self.ok(data=ProductVariantSerializer(variant).data)

    def destroy(self, request, pk=None):
        variant = selectors.get_variant_by_id(pk)
        if not variant:
            raise NotFoundError("Variant not found.")
        services.delete_variant(variant=variant)
        return self.ok(message="Variant deleted.")


class AttributeViewSet(BaseViewSet):
    """
    Admin CRUD for global catalog attributes.
    """
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]
    queryset = GlobalAttribute.objects.prefetch_related("options", "product_configs")

    def list(self, request):
        qs = selectors.get_all_global_attributes(
            search=request.query_params.get("search"),
        )
        return self.ok(data=AttributeAdminSerializer(qs, many=True).data)

    def retrieve(self, request, pk=None):
        attribute = selectors.get_global_attribute_by_id(pk)
        if not attribute:
            raise NotFoundError("Attribute not found.")
        return self.ok(data=AttributeAdminSerializer(attribute).data)

    def create(self, request):
        s = AttributeAdminWriteSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        attribute = services.create_global_attribute(
            name=s.validated_data["name"].strip(),
            options=s.validated_data.get("options", []),
            sort_order=s.validated_data.get("sort_order", 0),
            is_active=s.validated_data.get("is_active", True),
        )
        attribute = selectors.get_global_attribute_by_id(attribute.id)
        return self.created(data=AttributeAdminSerializer(attribute).data)

    def partial_update(self, request, pk=None):
        attribute = selectors.get_global_attribute_by_id(pk)
        if not attribute:
            raise NotFoundError("Attribute not found.")

        s = AttributeAdminWriteSerializer(data=request.data, partial=True)
        s.is_valid(raise_exception=True)

        attribute = services.update_global_attribute(
            attribute=attribute,
            name=s.validated_data.get("name"),
            options=s.validated_data.get("options") if "options" in s.validated_data else None,
            sort_order=s.validated_data.get("sort_order"),
            is_active=s.validated_data.get("is_active"),
        )
        attribute = selectors.get_global_attribute_by_id(attribute.id)
        return self.ok(data=AttributeAdminSerializer(attribute).data, message="Attribute updated.")

    def destroy(self, request, pk=None):
        attribute = selectors.get_global_attribute_by_id(pk)
        if not attribute:
            raise NotFoundError("Attribute not found.")
        services.delete_global_attribute(attribute=attribute)
        return self.ok(message="Attribute deleted.")
