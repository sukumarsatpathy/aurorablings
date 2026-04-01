from rest_framework import serializers
from core.media import build_media_url
from .models import (
    Warehouse, WarehouseStock, StockLedger,
    StockReservation, MovementType, ReferenceType,
)


class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Warehouse
        fields = ["id", "name", "code", "type", "address", "is_active", "is_default"]
        read_only_fields = ["id"]


class WarehouseStockSerializer(serializers.ModelSerializer):
    variant_id     = serializers.UUIDField(source="variant.id", read_only=True)
    warehouse_id   = serializers.UUIDField(source="warehouse.id", read_only=True)
    sku            = serializers.CharField(source="variant.sku", read_only=True)
    variant_name   = serializers.CharField(source="variant.name", read_only=True)
    product_name   = serializers.CharField(source="variant.product.name", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)
    is_in_stock    = serializers.BooleanField(read_only=True)
    is_low_stock   = serializers.BooleanField(read_only=True)

    class Meta:
        model  = WarehouseStock
        fields = [
            "id", "variant_id", "warehouse_id",
            "sku", "variant_name", "product_name",
            "warehouse_name", "warehouse_code",
            "on_hand", "reserved", "available",
            "low_stock_threshold",
            "is_in_stock", "is_low_stock",
            "updated_at",
        ]
        read_only_fields = fields


class WarehouseStockUpdateSerializer(serializers.Serializer):
    low_stock_threshold = serializers.IntegerField(min_value=0, max_value=9999)


class VariantOptionSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    sku = serializers.CharField()
    name = serializers.CharField(allow_blank=True)
    product_name = serializers.CharField(source="product.name")
    category_name = serializers.CharField(source="product.category.name", read_only=True)
    product_image = serializers.SerializerMethodField()
    is_active = serializers.BooleanField()
    price = serializers.DecimalField(max_digits=12, decimal_places=2, source="effective_price", read_only=True)

    def get_product_image(self, obj) -> str | None:
        product = getattr(obj, "product", None)
        if not product:
            return None

        media_items = list(product.media.all())
        if not media_items:
            return None

        primary = next((item for item in media_items if item.is_primary), None)
        image = (primary or media_items[0]).image
        return build_media_url(image, request=self.context.get("request"))


class StockLedgerSerializer(serializers.ModelSerializer):
    sku            = serializers.CharField(source="stock_record.variant.sku", read_only=True)
    warehouse_code = serializers.CharField(source="stock_record.warehouse.code", read_only=True)
    created_by_email = serializers.SerializerMethodField()

    class Meta:
        model  = StockLedger
        fields = [
            "id", "sku", "warehouse_code",
            "movement_type", "reference_type", "reference_id",
            "quantity",
            "on_hand_after", "reserved_after", "available_after",
            "notes", "created_by_email", "created_at",
        ]
        read_only_fields = fields

    def get_created_by_email(self, obj) -> str | None:
        return obj.created_by.email if obj.created_by else None


class StockReservationSerializer(serializers.ModelSerializer):
    sku            = serializers.CharField(source="stock_record.variant.sku", read_only=True)
    warehouse_code = serializers.CharField(source="stock_record.warehouse.code", read_only=True)

    class Meta:
        model  = StockReservation
        fields = [
            "id", "sku", "warehouse_code",
            "reference_type", "reference_id",
            "quantity", "status", "expires_at",
            "created_at", "updated_at",
        ]
        read_only_fields = fields


# ── Write serializers ─────────────────────────────────────────

class ReceiveStockSerializer(serializers.Serializer):
    variant_id   = serializers.UUIDField()
    warehouse_id = serializers.UUIDField()
    quantity     = serializers.IntegerField(min_value=1)
    reference_id = serializers.CharField(required=False, allow_blank=True, default="")
    notes        = serializers.CharField(required=False, allow_blank=True, default="")


class AdjustStockSerializer(serializers.Serializer):
    variant_id     = serializers.UUIDField()
    warehouse_id   = serializers.UUIDField()
    quantity_delta = serializers.IntegerField()      # signed: pos = in, neg = out
    reason         = serializers.CharField()


class TransferStockSerializer(serializers.Serializer):
    variant_id         = serializers.UUIDField()
    from_warehouse_id  = serializers.UUIDField()
    to_warehouse_id    = serializers.UUIDField()
    quantity           = serializers.IntegerField(min_value=1)
    notes              = serializers.CharField(required=False, allow_blank=True, default="")


class ReserveStockSerializer(serializers.Serializer):
    variant_id   = serializers.UUIDField()
    warehouse_id = serializers.UUIDField()
    quantity     = serializers.IntegerField(min_value=1)
    order_id     = serializers.CharField()


class ReleaseReservationSerializer(serializers.Serializer):
    order_id     = serializers.CharField()
    notes        = serializers.CharField(required=False, allow_blank=True, default="Order cancelled")


class ProcessReturnSerializer(serializers.Serializer):
    variant_id       = serializers.UUIDField()
    warehouse_id     = serializers.UUIDField()
    quantity         = serializers.IntegerField(min_value=1)
    return_id        = serializers.CharField()
    return_to_stock  = serializers.BooleanField(default=True)
    notes            = serializers.CharField(required=False, allow_blank=True, default="")


class ProcessExchangeSerializer(serializers.Serializer):
    exchange_id          = serializers.CharField()
    warehouse_id         = serializers.UUIDField()
    outgoing_variant_id  = serializers.UUIDField()
    outgoing_quantity    = serializers.IntegerField(min_value=1)
    incoming_variant_id  = serializers.UUIDField()
    incoming_quantity    = serializers.IntegerField(min_value=1)
    notes                = serializers.CharField(required=False, allow_blank=True, default="")


class AvailabilityCheckSerializer(serializers.Serializer):
    variant_id   = serializers.UUIDField()
    quantity     = serializers.IntegerField(min_value=1)
    warehouse_id = serializers.UUIDField(required=False, allow_null=True)
