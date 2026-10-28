"""
Bulk Receive — record a whole delivery (many products, many variants) in one save.

    GET  /api/v1/inventory/stock/bulk-receive/catalog/?warehouse_id=
         Every product that isn't deleted (drafts included), with its variants,
         their options (Color/Size + swatch colour) and current stock in that
         warehouse. The page builds the colour × size grids from this and
         matches CSV SKUs against it, so it's loaded once.

    POST /api/v1/inventory/stock/bulk-receive/
         {warehouse_id, reference_id?, notes?, items: [{variant_id, quantity}]}
         All lines are received inside one transaction: if any line fails,
         nothing is saved. Each line is an ordinary receive (own ledger entry,
         audit row), exactly as if it had been entered one at a time.

Kept in its own module so the main inventory views/services stay untouched.
"""

from __future__ import annotations

import uuid
from collections import OrderedDict

from django.db import transaction
from django.db.models import Prefetch
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.permissions import IsStaffOrAdmin
from apps.catalog.media import variant_photo
from apps.catalog.models import Attribute, Product, ProductVariant
from core.exceptions import NotFoundError, ValidationError
from core.media import build_media_url
from core.response import success_response

from . import services
from .models import Warehouse, WarehouseStock

MAX_LINES = 500
MAX_QUANTITY_PER_LINE = 100_000


# ─────────────────────────────────────────────────────────────
#  Service
# ─────────────────────────────────────────────────────────────

@transaction.atomic
def bulk_receive_stock(*, warehouse_id, items, reference_id: str = "", notes: str = "", created_by=None) -> dict:
    """
    Receive many lines at once. `items` = [{"variant_id", "quantity"}].
    Lines for the same variant are added together. All-or-nothing.
    """
    warehouse = Warehouse.objects.filter(pk=warehouse_id, is_active=True).first()
    if warehouse is None:
        raise ValidationError("Choose an active warehouse.")

    merged: "OrderedDict[str, int]" = OrderedDict()
    for item in items:
        variant_id = str(item["variant_id"])
        merged[variant_id] = merged.get(variant_id, 0) + int(item["quantity"])
    if not merged:
        raise ValidationError("Enter a quantity for at least one item.")
    if len(merged) > MAX_LINES:
        raise ValidationError(f"Up to {MAX_LINES} lines per save. Split the delivery into smaller parts.")

    variants = {
        str(v.pk): v
        for v in ProductVariant.objects.select_related("product").filter(
            pk__in=list(merged), product__deleted_at__isnull=True,
        )
    }
    unknown = [vid for vid in merged if vid not in variants]
    if unknown:
        raise ValidationError(
            f"{len(unknown)} item{'s' if len(unknown) != 1 else ''} no longer exist or belong to a deleted product. "
            "Reload the page and try again."
        )

    lines = []
    for variant_id, quantity in merged.items():
        if quantity <= 0 or quantity > MAX_QUANTITY_PER_LINE:
            raise ValidationError(f"Quantity for {variants[variant_id].sku} must be between 1 and {MAX_QUANTITY_PER_LINE}.")
        entry = services.receive_stock(
            variant_id=variant_id,
            warehouse_id=warehouse.pk,
            quantity=quantity,
            reference_id=reference_id,
            notes=notes,
            created_by=created_by,
        )
        lines.append({
            "variant_id": variant_id,
            "sku": variants[variant_id].sku,
            "quantity": quantity,
            "on_hand_after": entry.stock_record.on_hand,
        })

    return {
        "warehouse_id": str(warehouse.pk),
        "lines": lines,
        "total_quantity": sum(line["quantity"] for line in lines),
        "variants": len(lines),
        "products": len({variants[line["variant_id"]].product_id for line in lines}),
    }


# ─────────────────────────────────────────────────────────────
#  Serializers
# ─────────────────────────────────────────────────────────────

class BulkReceiveItemSerializer(serializers.Serializer):
    variant_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1, max_value=MAX_QUANTITY_PER_LINE)


class BulkReceiveSerializer(serializers.Serializer):
    warehouse_id = serializers.UUIDField()
    reference_id = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    items = BulkReceiveItemSerializer(many=True, allow_empty=False, max_length=MAX_LINES)


def _catalog(*, warehouse_id, request) -> list[dict]:
    stock_qs = WarehouseStock.objects.filter(warehouse_id=warehouse_id) if warehouse_id else WarehouseStock.objects.none()
    products = (
        Product.objects  # default manager hides deleted products
        .select_related("category")
        .prefetch_related(
            "media",
            Prefetch("attributes", queryset=Attribute.objects.prefetch_related("values").order_by("sort_order", "name")),
            Prefetch(
                "variants",
                queryset=ProductVariant.objects.prefetch_related(
                    "attribute_values__attribute",
                    Prefetch("stock_records", queryset=stock_qs, to_attr="stock_here"),
                ).order_by("sku"),
            ),
        )
        .order_by("name")
    )
    rows = []
    for product in products:
        media = list(product.media.all())
        main = variant_photo(None, media)
        variants = []
        for variant in product.variants.all():
            photo = variant_photo(variant, media)
            here = variant.stock_here[0] if variant.stock_here else None
            variants.append({
                "id": str(variant.pk),
                "sku": variant.sku,
                "name": variant.name,
                # For the label page, which works from this same catalogue.
                "barcode": variant.barcode,
                "label_text": variant.label_text,
                "price": str(variant.price),
                "is_active": variant.is_active,
                "on_hand": here.on_hand if here else 0,
                "available": here.available if here else 0,
                "image": build_media_url(photo.image_small or photo.image, request=request) if photo else None,
                "options": [
                    {"attribute": av.attribute.name, "value": av.value, "hex_code": getattr(av, "hex_code", "")}
                    for av in variant.attribute_values.all()
                ],
            })
        if not variants:
            continue
        rows.append({
            "id": str(product.pk),
            "name": product.name,
            "stock_id": product.stock_id,
            "is_active": product.is_active,
            "category": product.category.name if product.category_id else "",
            "image": build_media_url(main.image_small or main.image, request=request) if main else None,
            "attributes": [
                {
                    "name": attr.name,
                    "show_swatches": getattr(attr, "show_swatches", False),
                    "values": [{"value": v.value, "hex_code": getattr(v, "hex_code", "")} for v in attr.values.all()],
                }
                for attr in product.attributes.all()
            ],
            "variants": variants,
        })
    return rows


# ─────────────────────────────────────────────────────────────
#  Views
# ─────────────────────────────────────────────────────────────

class BulkReceiveCatalogView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def get(self, request):
        warehouse_id = request.query_params.get("warehouse_id") or None
        if warehouse_id:
            try:
                uuid.UUID(str(warehouse_id))
            except ValueError:
                raise ValidationError("Invalid warehouse.")
            if not Warehouse.objects.filter(pk=warehouse_id).exists():
                raise NotFoundError("Warehouse not found.")
        return success_response(
            data=_catalog(warehouse_id=warehouse_id, request=request),
            request_id=getattr(request, "request_id", None),
        )


class BulkReceiveView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request):
        s = BulkReceiveSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        result = bulk_receive_stock(created_by=request.user, **s.validated_data)
        return success_response(
            data=result,
            message=(
                f"Received {result['total_quantity']} piece{'s' if result['total_quantity'] != 1 else ''} "
                f"across {result['variants']} item{'s' if result['variants'] != 1 else ''}."
            ),
            request_id=getattr(request, "request_id", None),
        )
