"""
inventory.views
~~~~~~~~~~~~~~~
All inventory endpoints require IsAuthenticated + IsStaffOrAdmin
(stock data is internal — not public).
"""
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.permissions import IsStaffOrAdmin, IsAdminUser
from core.response import success_response
from core.viewsets import BaseViewSet
from core.exceptions import NotFoundError, ConflictError
from core.logging import get_logger

from . import services, selectors
from .models import WarehouseStock
from .serializers import (
    WarehouseSerializer,
    WarehouseStockSerializer,
    WarehouseStockUpdateSerializer,
    VariantOptionSerializer,
    StockLedgerSerializer,
    StockReservationSerializer,
    ReceiveStockSerializer,
    AdjustStockSerializer,
    TransferStockSerializer,
    ReserveStockSerializer,
    ReleaseReservationSerializer,
    ProcessReturnSerializer,
    ProcessExchangeSerializer,
    AvailabilityCheckSerializer,
)

logger = get_logger(__name__)
_STAFF = [IsAuthenticated, IsStaffOrAdmin]
_ADMIN = [IsAuthenticated, IsAdminUser]


# ─────────────────────────────────────────────────────────────
#  Warehouse CRUD
# ─────────────────────────────────────────────────────────────

class WarehouseViewSet(BaseViewSet):
    """
    GET    /warehouses/       → list
    GET    /warehouses/{id}/  → detail
    POST   /warehouses/       → create  [admin]
    PATCH  /warehouses/{id}/  → update  [admin]
    """
    queryset = selectors.get_all_warehouses()

    def get_permissions(self):
        if self.action in ("create", "partial_update", "destroy"):
            return [p() for p in _ADMIN]
        return [p() for p in _STAFF]

    def list(self, request):
        include_inactive = request.query_params.get("include_inactive", "false").lower() == "true"
        qs = selectors.get_all_warehouses(active_only=not include_inactive)
        return self.paginate(qs, WarehouseSerializer)

    def retrieve(self, request, pk=None):
        wh = selectors.get_warehouse_by_id(pk)
        if not wh:
            raise NotFoundError("Warehouse not found.")
        return self.ok(data=WarehouseSerializer(wh).data)

    def create(self, request):
        s = WarehouseSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        wh = services.create_warehouse(**s.validated_data)
        return self.created(data=WarehouseSerializer(wh).data)

    def partial_update(self, request, pk=None):
        wh = selectors.get_warehouse_by_id(pk)
        if not wh:
            raise NotFoundError("Warehouse not found.")
        s = WarehouseSerializer(wh, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        return self.ok(data=WarehouseSerializer(wh).data)

    def destroy(self, request, pk=None):
        wh = selectors.get_warehouse_by_id(pk)
        if not wh:
            raise NotFoundError("Warehouse not found.")
        has_stock_records = WarehouseStock.objects.filter(warehouse_id=wh.id).exists()
        if has_stock_records:
            raise ConflictError(
                "Cannot delete warehouse with stock history. Mark it inactive instead."
            )
        wh.delete()
        return self.ok(message="Warehouse deleted successfully.")


# ─────────────────────────────────────────────────────────────
#  Stock Levels
# ─────────────────────────────────────────────────────────────

class StockLevelView(APIView):
    """
    GET /stock/variant/{variant_id}/            → stock across all warehouses
    GET /stock/variant/{variant_id}/check/?quantity=5  → availability check
    """
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def get(self, request, variant_id):
        records = selectors.get_stock_across_warehouses(variant_id)
        return success_response(
            data=WarehouseStockSerializer(records, many=True).data,
            request_id=self.request.request_id if hasattr(request, "request_id") else None,
        )


class StockRecordListView(APIView):
    """
    GET /stock/?search=&warehouse_id=&status=in|low|out
    """
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def get(self, request):
        records = selectors.get_all_stock_records(
            search=request.query_params.get("search"),
            warehouse_id=request.query_params.get("warehouse_id"),
            status=request.query_params.get("status"),
        )
        return success_response(
            data=WarehouseStockSerializer(records, many=True).data,
            request_id=getattr(request, "request_id", None),
        )


class StockRecordDetailView(APIView):
    """
    GET   /stock/{stock_record_id}/
    PATCH /stock/{stock_record_id}/   (low_stock_threshold only)
    """
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def get(self, request, pk):
        record = selectors.get_stock_record_by_id(pk)
        if not record:
            raise NotFoundError("Stock record not found.")
        return success_response(
            data=WarehouseStockSerializer(record).data,
            request_id=getattr(request, "request_id", None),
        )

    def patch(self, request, pk):
        record = selectors.get_stock_record_by_id(pk)
        if not record:
            raise NotFoundError("Stock record not found.")
        s = WarehouseStockUpdateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        record.low_stock_threshold = s.validated_data["low_stock_threshold"]
        record.save(update_fields=["low_stock_threshold", "updated_at"])
        return success_response(
            data=WarehouseStockSerializer(record).data,
            message="Stock threshold updated.",
            request_id=getattr(request, "request_id", None),
        )


class VariantOptionsView(APIView):
    """
    GET /stock/variants/?search=&active_only=true
    """
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def get(self, request):
        active_only = request.query_params.get("active_only", "true").lower() != "false"
        variants = selectors.get_variant_options(
            search=request.query_params.get("search"),
            active_only=active_only,
        )
        serializer = VariantOptionSerializer(
            variants,
            many=True,
            context={"request": request},
        )
        return success_response(
            data=serializer.data,
            request_id=getattr(request, "request_id", None),
        )


class AvailabilityCheckView(APIView):
    """
    POST /stock/availability/
    Body: { variant_id, quantity, warehouse_id? }
    No lock — for display only.  Use reserve_stock for actual holds.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        s = AvailabilityCheckSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        result = selectors.check_availability(
            s.validated_data["variant_id"],
            s.validated_data["quantity"],
            s.validated_data.get("warehouse_id"),
        )
        return success_response(data=result, request_id=getattr(request, "request_id", None))


class LowStockView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def get(self, request):
        threshold = request.query_params.get("threshold")
        records = selectors.get_low_stock_records(int(threshold) if threshold else None)
        return success_response(
            data=WarehouseStockSerializer(records, many=True).data,
            request_id=getattr(request, "request_id", None),
        )


# ─────────────────────────────────────────────────────────────
#  Stock Operations
# ─────────────────────────────────────────────────────────────

class ReceiveStockView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request):
        s = ReceiveStockSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        entry = services.receive_stock(created_by=request.user, **s.validated_data)
        return success_response(
            data=StockLedgerSerializer(entry).data,
            message="Stock received successfully.",
            request_id=getattr(request, "request_id", None),
        )


class AdjustStockView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request):
        s = AdjustStockSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        entry = services.adjust_stock(created_by=request.user, **s.validated_data)
        return success_response(
            data=StockLedgerSerializer(entry).data,
            message="Adjustment applied.",
            request_id=getattr(request, "request_id", None),
        )


class TransferStockView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request):
        s = TransferStockSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        result = services.transfer_stock(created_by=request.user, **s.validated_data)
        return success_response(
            data={
                "out": StockLedgerSerializer(result["out"]).data,
                "in":  StockLedgerSerializer(result["in"]).data,
            },
            message="Stock transferred.",
            request_id=getattr(request, "request_id", None),
        )


class ReserveStockView(APIView):
    """Internal endpoint — called by the Order service."""
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request):
        s = ReserveStockSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        reservation = services.reserve_stock(created_by=request.user, **s.validated_data)
        return success_response(
            data=StockReservationSerializer(reservation).data,
            message="Stock reserved.",
            request_id=getattr(request, "request_id", None),
        )


class ReleaseReservationView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request):
        s = ReleaseReservationSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        released = services.release_reservation(created_by=request.user, **s.validated_data)
        return success_response(
            data=StockReservationSerializer(released, many=True).data,
            message=f"{len(released)} reservation(s) released.",
            request_id=getattr(request, "request_id", None),
        )


class ProcessReturnView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request):
        s = ProcessReturnSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        entry = services.process_return(created_by=request.user, **s.validated_data)
        return success_response(
            data=StockLedgerSerializer(entry).data if entry else None,
            message="Return processed.",
            request_id=getattr(request, "request_id", None),
        )


class ProcessExchangeView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request):
        s = ProcessExchangeSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        result = services.process_exchange(created_by=request.user, **s.validated_data)
        return success_response(
            data={
                "out": StockLedgerSerializer(result["out"]).data,
                "in":  StockLedgerSerializer(result["in"]).data,
            },
            message="Exchange processed.",
            request_id=getattr(request, "request_id", None),
        )


# ─────────────────────────────────────────────────────────────
#  Ledger History
# ─────────────────────────────────────────────────────────────

class StockLedgerView(APIView):
    """GET /stock/ledger/?variant_id=&warehouse_id=&movement_type="""
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def get(self, request):
        variant_id    = request.query_params.get("variant_id")
        warehouse_id  = request.query_params.get("warehouse_id")
        movement_type = request.query_params.get("movement_type")
        limit         = int(request.query_params.get("limit", 100))

        if not variant_id:
            return self.bad_request("variant_id is required.")

        entries = selectors.get_ledger_for_variant(
            variant_id=variant_id,
            warehouse_id=warehouse_id,
            movement_type=movement_type,
            limit=limit,
        )
        return success_response(
            data=StockLedgerSerializer(entries, many=True).data,
            request_id=getattr(request, "request_id", None),
        )

    def bad_request(self, msg):
        from core.response import error_response
        return error_response(message=msg, error_code="bad_request", status_code=400)


class RecomputeStockView(APIView):
    """POST /stock/recompute/{stock_record_id}/  — admin only."""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request, pk):
        from .models import WarehouseStock
        try:
            record = WarehouseStock.objects.get(pk=pk)
        except WarehouseStock.DoesNotExist:
            raise NotFoundError("Stock record not found.")
        updated = services.recompute_stock(stock_record=record)
        return success_response(
            data=WarehouseStockSerializer(updated).data,
            message="Stock recomputed from ledger.",
            request_id=getattr(request, "request_id", None),
        )
