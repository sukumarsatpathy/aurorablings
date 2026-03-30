from __future__ import annotations

from django.db import transaction
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView

from apps.accounts.permissions import IsStaffOrAdmin
from core.response import success_response, error_response
from core.exceptions import NotFoundError

from .models import Shipment
from .providers.shiprocket import ShiprocketProvider
from .serializers import ShipmentSerializer
from . import services
from .tasks import (
    retry_create_shipment,
    sync_tracking_for_shipment,
    request_pickup_for_shipment,
    process_shiprocket_webhook_event,
)


class ShipmentListView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def get(self, request):
        qs = services.list_shipments(
            status=request.query_params.get("status"),
            provider=request.query_params.get("provider"),
        )
        return success_response(data=ShipmentSerializer(qs, many=True).data)


class OrderShipmentDetailView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def get(self, request, order_id):
        shipment = services.get_shipment_for_order(str(order_id))
        if not shipment:
            return success_response(data=None)
        return success_response(data=ShipmentSerializer(shipment).data)


class ShipmentCreateView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request, order_id):
        force = bool(request.data.get("force", False))
        task = retry_create_shipment if force else None
        if task:
            task.delay(str(order_id))
        else:
            from .tasks import create_shipment_for_order

            create_shipment_for_order.delay(str(order_id))
        return success_response(message="Shipment sync queued.")


class ShipmentPickupView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request, shipment_id):
        shipment = Shipment.objects.filter(id=shipment_id).first()
        if not shipment:
            raise NotFoundError("Shipment not found.")
        request_pickup_for_shipment.delay(str(shipment_id))
        services.log_manual_action(
            user=request.user,
            action="Requested pickup from admin shipping action.",
            shipment=shipment,
            metadata={"shipment_id": str(shipment.id)},
            request=request,
        )
        return success_response(message="Pickup request queued.")


class ShipmentTrackingRefreshView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request, shipment_id):
        shipment = Shipment.objects.filter(id=shipment_id).first()
        if not shipment:
            raise NotFoundError("Shipment not found.")
        sync_tracking_for_shipment.delay(str(shipment_id))
        services.log_manual_action(
            user=request.user,
            action="Requested tracking refresh from admin shipping action.",
            shipment=shipment,
            metadata={"shipment_id": str(shipment.id)},
            request=request,
        )
        return success_response(message="Tracking sync queued.")


class ShipmentCancelView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request, shipment_id):
        shipment = services.cancel_shipment(shipment_id=str(shipment_id), changed_by=request.user)
        services.log_manual_action(
            user=request.user,
            action="Cancelled shipment from admin shipping action.",
            shipment=shipment,
            metadata={"shipment_id": str(shipment.id)},
            request=request,
        )
        return success_response(data=ShipmentSerializer(shipment).data, message="Shipment cancelled.")


class ShipmentPreflightView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def get(self, request, order_id):
        from apps.orders.selectors import get_order_by_id

        order = get_order_by_id(order_id)
        if not order:
            raise NotFoundError("Order not found.")
        result = services.preflight_validate_order(order)
        return success_response(data={"ok": result.ok, "errors": result.errors})


class TrackingWebhookView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        cfg = services.get_shiprocket_config()
        if cfg.get("webhook_enabled", True):
            expected = str(cfg.get("webhook_secret") or "").strip()
            provided = str(request.headers.get("x-api-key") or "").strip()
            if expected and expected != provided:
                return error_response(
                    message="Invalid webhook token.",
                    error_code="forbidden",
                    status_code=403,
                )

        payload = request.data if isinstance(request.data, dict) else {}
        idempotency_key = (
            str(request.headers.get("x-event-id") or "").strip()
            or ShiprocketProvider.build_event_idempotency_key(payload)
        )

        try:
            with transaction.atomic():
                event = services.create_webhook_event(payload=payload, idempotency_key=idempotency_key)
        except Exception:
            # Duplicate webhook event idempotency key.
            return success_response(message="Tracking update already processed.")

        process_shiprocket_webhook_event.delay(str(event.id))
        return success_response(message="Tracking update accepted.")
