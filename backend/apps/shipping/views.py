from __future__ import annotations

from django.db import transaction
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView

from apps.accounts.permissions import IsStaffOrAdmin
from core.response import success_response, error_response
from core.exceptions import NotFoundError

from .models import Shipment
from apps.orders.selectors import get_order_by_id
from .providers.shiprocket import ShiprocketProvider
from .providers.nimbuspost import NimbusPostProvider
from .serializers import (
    ShipmentSerializer,
    ShippingApprovalSerializer,
    LocalDeliveryStatusSerializer,
)
from . import services
from .tasks import (
    retry_create_shipment,
    sync_tracking_for_shipment,
    request_pickup_for_shipment,
    process_webhook_event,
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


class MyOrderShipmentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        order = get_order_by_id(order_id, user=request.user)
        if not order:
            raise NotFoundError("Order not found.")
        shipment = services.get_shipment_for_order(str(order.id))
        if not shipment:
            return success_response(
                data={
                    "order_id": str(order.id),
                    "order_number": order.order_number,
                    "shipping_approval_status": order.shipping_approval_status,
                    "fulfillment_method": order.fulfillment_method,
                    "shipment": None,
                }
            )
        return success_response(
            data={
                "order_id": str(order.id),
                "order_number": order.order_number,
                "shipping_approval_status": order.shipping_approval_status,
                "fulfillment_method": order.fulfillment_method,
                "shipment": ShipmentSerializer(shipment).data,
            }
        )


class ShippingApprovalView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request, order_id):
        order = get_order_by_id(order_id)
        if not order:
            raise NotFoundError("Order not found.")
        serializer = ShippingApprovalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        local_meta = {
            "rider_name": serializer.validated_data.get("rider_name", ""),
            "rider_phone": serializer.validated_data.get("rider_phone", ""),
            "notes": serializer.validated_data.get("local_notes", ""),
            "expected_delivery_date": serializer.validated_data.get("local_expected_delivery_date"),
            "local_status": "assigned",
        }
        updated = services.approve_order_shipping(
            order_id=str(order.id),
            fulfillment_method=serializer.validated_data["fulfillment_method"],
            approved_by=request.user,
            notes=serializer.validated_data.get("notes", ""),
            local_meta=local_meta,
        )
        shipment = services.get_shipment_for_order(str(updated.id))
        return success_response(
            data={
                "order_id": str(updated.id),
                "shipping_approval_status": updated.shipping_approval_status,
                "fulfillment_method": updated.fulfillment_method,
                "shipment": ShipmentSerializer(shipment).data if shipment else None,
            },
            message="Shipping approved.",
        )


class LocalDeliveryStatusUpdateView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request, shipment_id):
        shipment = Shipment.objects.filter(id=shipment_id).first()
        if not shipment:
            raise NotFoundError("Shipment not found.")
        serializer = LocalDeliveryStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        shipment.local_delivery_status = serializer.validated_data["local_delivery_status"]
        shipment.local_rider_name = serializer.validated_data.get("rider_name", shipment.local_rider_name)
        shipment.local_rider_phone = serializer.validated_data.get("rider_phone", shipment.local_rider_phone)
        shipment.local_notes = serializer.validated_data.get("local_notes", shipment.local_notes)
        eta = serializer.validated_data.get("local_expected_delivery_date")
        if eta is not None:
            shipment.local_expected_delivery_date = eta
        shipment.status = shipment.local_delivery_status
        shipment.save()
        return success_response(data=ShipmentSerializer(shipment).data, message="Local delivery status updated.")


class ShipmentCreateView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request, order_id):
        force = bool(request.data.get("force", False))
        try:
            task = retry_create_shipment if force else None
            if task:
                task.delay(str(order_id))
            else:
                from .tasks import create_shipment_for_order

                create_shipment_for_order.delay(str(order_id))
            return success_response(message="Shipment sync queued.")
        except Exception:
            shipment = services.create_or_update_shipment_for_order(order_id=str(order_id), force=force)
            return success_response(data=ShipmentSerializer(shipment).data, message="Shipment created.")


class ShipmentPickupView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request, shipment_id):
        shipment = Shipment.objects.filter(id=shipment_id).first()
        if not shipment:
            raise NotFoundError("Shipment not found.")
        try:
            request_pickup_for_shipment.delay(str(shipment_id))
            message = "Pickup request queued."
        except Exception:
            shipment = services.request_pickup_for_shipment(shipment_id=str(shipment_id))
            message = f"Pickup requested. Status: {shipment.status}"
        services.log_manual_action(
            user=request.user,
            action="Requested pickup from admin shipping action.",
            shipment=shipment,
            metadata={"shipment_id": str(shipment.id)},
            request=request,
        )
        return success_response(message=message)


class ShipmentTrackingRefreshView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request, shipment_id):
        shipment = Shipment.objects.filter(id=shipment_id).first()
        if not shipment:
            raise NotFoundError("Shipment not found.")
        try:
            sync_tracking_for_shipment.delay(str(shipment_id))
            message = "Tracking sync queued."
        except Exception:
            shipment = services.sync_tracking(shipment_id=str(shipment_id))
            message = f"Tracking refreshed. Status: {shipment.status}"
        services.log_manual_action(
            user=request.user,
            action="Requested tracking refresh from admin shipping action.",
            shipment=shipment,
            metadata={"shipment_id": str(shipment.id)},
            request=request,
        )
        return success_response(message=message)


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
                event = services.create_webhook_event(payload=payload, idempotency_key=idempotency_key, provider_name="shiprocket")
        except Exception:
            # Duplicate webhook event idempotency key.
            return success_response(message="Tracking update already processed.")

        process_webhook_event.delay(str(event.id))
        return success_response(message="Tracking update accepted.")


class NimbusPostWebhookView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        body = request.body or b""
        signature = str(request.headers.get("x-nimbus-signature") or "").strip()
        if not NimbusPostProvider.verify_webhook_signature(body=body, signature=signature):
            return error_response(message="Invalid NimbusPost webhook signature.", error_code="forbidden", status_code=403)

        payload = request.data if isinstance(request.data, dict) else {}
        idempotency_key = (
            str(request.headers.get("x-event-id") or "").strip()
            or NimbusPostProvider.build_event_idempotency_key(payload)
        )
        try:
            with transaction.atomic():
                event = services.create_webhook_event(payload=payload, idempotency_key=idempotency_key, provider_name="nimbuspost")
        except Exception:
            return success_response(message="NimbusPost webhook already processed.")

        # Reuse generic webhook processor; provider is inferred from matched shipment.
        process_webhook_event.delay(str(event.id))
        return success_response(message="NimbusPost tracking update accepted.")
