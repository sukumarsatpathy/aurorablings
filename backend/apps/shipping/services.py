from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.features import services as feature_services
from apps.orders.models import (
    Order,
    OrderStatus,
    FulfillmentMethod,
    ShippingApprovalStatus,
)
from apps.orders import services as order_services
from audit.models import ActorType, AuditAction
from audit.services.activity_logger import log_activity
from core.exceptions import ConflictError, ValidationError, NotFoundError
from core.logging import get_logger

from .models import Shipment, ShipmentEvent, ShipmentEventSource, ShipmentProvider, ShipmentStatus
from .providers.registry import registry

logger = get_logger(__name__)


class ShippingError(Exception):
    def __init__(self, message: str, code: str = "shipping_error"):
        super().__init__(message)
        self.code = code


@dataclass
class PreflightResult:
    ok: bool
    errors: list[str]


def get_provider_config() -> dict:
    return feature_services.get_setting("shipping.provider", default={}) or {}


def get_shiprocket_config() -> dict:
    return feature_services.get_setting("shipping.shiprocket", default={}) or {}


def get_active_provider_name() -> str:
    cfg = get_provider_config()
    if not cfg or not cfg.get("enabled", False):
        return ""
    return str(cfg.get("active") or "").strip().lower()


def resolve_provider():
    name = get_active_provider_name()
    if not name:
        raise ShippingError("Shipping provider is disabled.", code="config_error")
    return registry.get(name)


def provider_name_for_fulfillment(method: str) -> str:
    mapped = {
        FulfillmentMethod.SHIPROCKET: ShipmentProvider.SHIPROCKET,
        FulfillmentMethod.NIMBUSPOST: ShipmentProvider.NIMBUSPOST,
        FulfillmentMethod.LOCAL_DELIVERY: ShipmentProvider.LOCAL_DELIVERY,
    }
    return mapped.get(method, "")


def resolve_provider_for_order(order: Order):
    provider_name = provider_name_for_fulfillment(order.fulfillment_method)
    if not provider_name:
        raise ShippingError("Fulfillment method is not selected for this order.", code="validation_error")
    return registry.get(provider_name)


def resolve_provider_for_shipment(shipment: Shipment):
    provider_name = str(shipment.provider or "").strip().lower()
    if not provider_name:
        raise ShippingError("Shipment provider is not set.", code="validation_error")
    return registry.get(provider_name)


@transaction.atomic
def approve_order_shipping(
    *,
    order_id: str,
    fulfillment_method: str,
    approved_by=None,
    notes: str = "",
    local_meta: dict | None = None,
) -> Order:
    order = Order.objects.select_for_update().get(id=order_id)
    method = str(fulfillment_method or "").strip().lower()
    if method not in {FulfillmentMethod.LOCAL_DELIVERY, FulfillmentMethod.NIMBUSPOST, FulfillmentMethod.SHIPROCKET}:
        raise ValidationError("Invalid fulfillment method.")

    order.fulfillment_method = method
    order.shipping_approval_status = ShippingApprovalStatus.APPROVED
    order.shipping_approved_at = timezone.now()
    order.shipping_approved_by = approved_by
    order.shipping_approval_notes = notes or ""
    order.save(
        update_fields=[
            "fulfillment_method",
            "shipping_approval_status",
            "shipping_approved_at",
            "shipping_approved_by",
            "shipping_approval_notes",
            "updated_at",
        ]
    )

    # Ensure a shipment shell exists immediately after approval for audit visibility.
    shipment, _ = Shipment.objects.get_or_create(
        order=order,
        defaults={
            "provider": provider_name_for_fulfillment(method) or ShipmentProvider.LOCAL_DELIVERY,
            "status": ShipmentStatus.APPROVED,
            "approved_at": timezone.now(),
        },
    )
    shipment.provider = provider_name_for_fulfillment(method) or shipment.provider
    shipment.status = ShipmentStatus.APPROVED
    shipment.approved_at = timezone.now()
    if method == FulfillmentMethod.LOCAL_DELIVERY:
        local_meta = local_meta or {}
        shipment.local_rider_name = str(local_meta.get("rider_name") or shipment.local_rider_name or "").strip()
        shipment.local_rider_phone = str(local_meta.get("rider_phone") or shipment.local_rider_phone or "").strip()
        shipment.local_notes = str(local_meta.get("notes") or shipment.local_notes or "").strip()
        shipment.local_delivery_status = str(local_meta.get("local_status") or shipment.local_delivery_status or ShipmentStatus.ASSIGNED).strip()
        eta = local_meta.get("expected_delivery_date")
        if eta:
            shipment.local_expected_delivery_date = eta
    shipment.save()

    _create_event(
        shipment=shipment,
        source=ShipmentEventSource.MANUAL,
        provider_status="shipping_approved",
        internal_status=shipment.status,
        payload={
            "fulfillment_method": method,
            "approved_by": str(getattr(approved_by, "id", "") or ""),
            "notes": notes or "",
            "local_meta": {
                **(local_meta or {}),
                "expected_delivery_date": (
                    local_meta.get("expected_delivery_date").isoformat()
                    if local_meta and local_meta.get("expected_delivery_date")
                    else None
                ),
            },
        },
        idempotency_key=f"approval:{order.id}:{method}:{int(timezone.now().timestamp())}",
    )
    return order


def is_auto_create_enabled() -> bool:
    return bool(get_provider_config().get("auto_create_shipment", False))


def _map_shipping_status_to_order_status(shipment_status: str) -> str | None:
    if shipment_status in {ShipmentStatus.BOOKED, ShipmentStatus.ASSIGNED, ShipmentStatus.PICKED_UP, ShipmentStatus.IN_TRANSIT, ShipmentStatus.OUT_FOR_DELIVERY}:
        return OrderStatus.SHIPPED
    if shipment_status == ShipmentStatus.DELIVERED:
        return OrderStatus.DELIVERED
    if shipment_status in {ShipmentStatus.CANCELLED, ShipmentStatus.FAILED}:
        return OrderStatus.CANCELLED
    return None


def _set_order_shipping_fields(order: Order, shipment: Shipment) -> None:
    order.tracking_number = shipment.awb_code
    order.shipping_carrier = shipment.courier_name
    order.save(update_fields=["tracking_number", "shipping_carrier", "updated_at"])


def _create_event(
    *,
    shipment: Shipment | None,
    source: str,
    provider_status: str,
    internal_status: str,
    payload: dict,
    idempotency_key: str = "",
) -> ShipmentEvent:
    if idempotency_key:
        existing = ShipmentEvent.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            return existing

    return ShipmentEvent.objects.create(
        shipment=shipment,
        source=source,
        provider_status=provider_status,
        internal_status=internal_status,
        event_payload=payload,
        idempotency_key=idempotency_key,
    )


def preflight_validate_order(order: Order) -> PreflightResult:
    errors: list[str] = []
    shipping = order.shipping_address or {}

    if order.shipping_approval_status != ShippingApprovalStatus.APPROVED:
        errors.append("Shipping is not approved for this order.")

    if order.fulfillment_method == FulfillmentMethod.UNASSIGNED:
        errors.append("Fulfillment method is not selected.")

    if order.status not in {OrderStatus.PAID, OrderStatus.PROCESSING, OrderStatus.SHIPPED, OrderStatus.DELIVERED, OrderStatus.COMPLETED}:
        errors.append("Order must be paid/processing/shipped/delivered/completed for shipment creation.")

    if Shipment.objects.filter(order=order).exclude(
        status__in=[
            ShipmentStatus.CANCELLED,
            ShipmentStatus.FAILED,
            ShipmentStatus.PENDING_APPROVAL,
            ShipmentStatus.APPROVED,
        ]
    ).exists():
        errors.append("An active shipment already exists for this order.")

    if order.fulfillment_method != FulfillmentMethod.LOCAL_DELIVERY:
        if not shipping.get("full_name"):
            errors.append("Shipping address full_name is required.")
        if not shipping.get("line1"):
            errors.append("Shipping address line1 is required.")
        if not shipping.get("city"):
            errors.append("Shipping address city is required.")
        if not shipping.get("state"):
            errors.append("Shipping address state is required.")
        if not shipping.get("pincode"):
            errors.append("Shipping address pincode is required.")
        if not shipping.get("phone"):
            errors.append("Shipping address phone is required.")

    return PreflightResult(ok=(len(errors) == 0), errors=errors)


@transaction.atomic
def create_or_update_shipment_for_order(*, order_id: str, source: str = ShipmentEventSource.SYSTEM, force: bool = False) -> Shipment:
    order = (
        Order.objects.select_for_update()
        .prefetch_related("items")
        .get(id=order_id)
    )

    existing = Shipment.objects.filter(order=order).first()
    if existing and existing.external_shipment_id and not force:
        logger.info("shipment_create_skipped_existing", order_id=str(order.id), shipment_id=str(existing.id))
        return existing

    preflight = preflight_validate_order(order)
    if not preflight.ok:
        allowed_if_existing = (
            existing is not None
            and preflight.errors == ["An active shipment already exists for this order."]
            and force
        )
        if not allowed_if_existing:
            raise ValidationError("Shipment preflight validation failed.", extra={"errors": preflight.errors})

    selected_provider = provider_name_for_fulfillment(order.fulfillment_method)
    try:
        shipment, created = Shipment.objects.select_for_update().get_or_create(
            order=order,
            defaults={
                "provider": selected_provider or ShipmentProvider.LOCAL_DELIVERY,
                "status": ShipmentStatus.APPROVED,
            },
        )
    except IntegrityError as exc:
        raise ConflictError("Duplicate shipment create prevented.") from exc

    if not created and not force:
        if shipment.provider == ShipmentProvider.LOCAL_DELIVERY and shipment.status not in {ShipmentStatus.CANCELLED, ShipmentStatus.FAILED}:
            return shipment
        if shipment.external_shipment_id:
            logger.info("shipment_create_skipped_existing", order_id=str(order.id), shipment_id=str(shipment.id))
            return shipment

    provider = resolve_provider_for_order(order)
    shipment.provider = selected_provider or shipment.provider

    if shipment.provider != ShipmentProvider.LOCAL_DELIVERY and get_shiprocket_config().get("serviceability_check_enabled", False):
        serviceability = provider.verify_serviceability(order)
        if not serviceability.success:
            raise ShippingError(serviceability.error_message or "Serviceability check failed.", code=serviceability.error_code)

    create_result = provider.create_order(order)
    if not create_result.success:
        shipment.status = ShipmentStatus.FAILED
        shipment.error_code = create_result.error_code or "provider_error"
        shipment.error_message = create_result.error_message or "Failed to create order in shipping provider"
        shipment.raw_provider_response = create_result.data or {}
        shipment.save(update_fields=["status", "error_code", "error_message", "raw_provider_response", "updated_at"])
        raise ShippingError(shipment.error_message, code=shipment.error_code)

    shipment.status = create_result.status or ShipmentStatus.CREATED
    shipment.external_order_id = create_result.data.get("external_order_id", "")
    shipment.external_shipment_id = create_result.data.get("external_shipment_id", "")
    shipment.awb_code = create_result.data.get("awb_code", shipment.awb_code)
    shipment.courier_name = create_result.data.get("courier_name", shipment.courier_name)
    shipment.tracking_url = create_result.data.get("tracking_url", shipment.tracking_url)
    shipment.label_url = create_result.data.get("label_url", shipment.label_url)
    shipment.raw_provider_response = create_result.data.get("raw") or create_result.data
    shipment.error_code = ""
    shipment.error_message = ""
    shipment.approved_at = shipment.approved_at or timezone.now()
    shipment.save()

    _create_event(
        shipment=shipment,
        source=source,
        provider_status="order_created",
        internal_status=shipment.status,
        payload=create_result.data,
    )

    provider_cfg = get_provider_config()

    if shipment.provider == ShipmentProvider.LOCAL_DELIVERY:
        shipment.status = shipment.local_delivery_status or ShipmentStatus.ASSIGNED
        shipment.pickup_requested = False
        shipment.save(update_fields=["status", "pickup_requested", "updated_at"])
        _create_event(
            shipment=shipment,
            source=source,
            provider_status="local_assigned",
            internal_status=shipment.status,
            payload={"local_delivery": True},
        )
        _set_order_shipping_fields(order, shipment)
        return shipment

    if provider_cfg.get("auto_generate_awb", True):
        awb_result = provider.assign_awb(shipment)
        if awb_result.success:
            shipment.status = awb_result.status or ShipmentStatus.AWB_ASSIGNED
            shipment.awb_code = awb_result.data.get("awb_code", shipment.awb_code)
            shipment.courier_name = awb_result.data.get("courier_name", shipment.courier_name)
            shipment.courier_company_id = awb_result.data.get("courier_company_id", shipment.courier_company_id)
            shipment.raw_provider_response = awb_result.data.get("raw") or shipment.raw_provider_response
            shipment.save()
            _create_event(
                shipment=shipment,
                source=source,
                provider_status="awb_assigned",
                internal_status=shipment.status,
                payload=awb_result.data,
            )

    label_result = provider.generate_label(shipment)
    if label_result.success:
        shipment.label_url = label_result.data.get("label_url") or shipment.label_url
        shipment.save(update_fields=["label_url", "updated_at"])

    manifest_result = provider.generate_manifest(shipment)
    if manifest_result.success:
        shipment.manifest_url = manifest_result.data.get("manifest_url") or shipment.manifest_url
        shipment.save(update_fields=["manifest_url", "updated_at"])

    if provider_cfg.get("auto_request_pickup", False):
        request_pickup_for_shipment(shipment_id=str(shipment.id), source=source)

    try:
        from apps.invoices.services.invoice_service import InvoiceService

        shipment.invoice_url = InvoiceService.build_invoice_url(order_id=str(order.id))
        shipment.save(update_fields=["invoice_url", "updated_at"])
    except Exception:
        pass

    _set_order_shipping_fields(order, shipment)
    return shipment


@transaction.atomic
def request_pickup_for_shipment(*, shipment_id: str, source: str = ShipmentEventSource.MANUAL) -> Shipment:
    shipment = Shipment.objects.select_for_update().select_related("order").get(id=shipment_id)
    provider = resolve_provider_for_shipment(shipment)
    result = provider.request_pickup(shipment)
    if not result.success:
        raise ShippingError(result.error_message or "Pickup request failed", code=result.error_code)

    shipment.pickup_requested = True
    shipment.status = result.status or ShipmentStatus.PICKUP_REQUESTED
    shipment.pickup_scheduled_at = timezone.now()
    shipment.raw_provider_response = result.data.get("raw") or result.data
    shipment.save()

    _create_event(
        shipment=shipment,
        source=source,
        provider_status="pickup_requested",
        internal_status=shipment.status,
        payload=result.data,
    )
    return shipment


@transaction.atomic
def sync_tracking(*, shipment_id: str, source: str = ShipmentEventSource.POLLER) -> Shipment:
    shipment = Shipment.objects.select_for_update().select_related("order").get(id=shipment_id)
    provider = resolve_provider_for_shipment(shipment)
    result = provider.get_tracking(shipment)
    if not result.success:
        raise ShippingError(result.error_message or "Tracking sync failed", code=result.error_code)

    provider_status = result.data.get("provider_status", "")
    new_status = result.status or shipment.status

    shipment.status = new_status
    shipment.tracking_url = result.data.get("tracking_url") or shipment.tracking_url
    shipment.raw_provider_response = result.data.get("raw") or shipment.raw_provider_response
    if new_status == ShipmentStatus.DELIVERED and not shipment.delivered_at:
        shipment.delivered_at = timezone.now()
    if new_status in {ShipmentStatus.PICKED_UP, ShipmentStatus.IN_TRANSIT, ShipmentStatus.OUT_FOR_DELIVERY} and not shipment.shipped_at:
        shipment.shipped_at = timezone.now()
    shipment.save()

    _create_event(
        shipment=shipment,
        source=source,
        provider_status=provider_status,
        internal_status=new_status,
        payload=result.data,
    )

    _update_order_for_shipment_status(shipment, source=source)
    _set_order_shipping_fields(shipment.order, shipment)
    return shipment


def _update_order_for_shipment_status(shipment: Shipment, *, source: str) -> None:
    target_order_status = _map_shipping_status_to_order_status(shipment.status)
    if not target_order_status:
        return

    order = shipment.order
    if order.status == target_order_status:
        return

    try:
        if target_order_status == OrderStatus.SHIPPED:
            if order.status == OrderStatus.PAID:
                order_services.transition_order(
                    order=order,
                    new_status=OrderStatus.PROCESSING,
                    notes="Moved to processing from shipping webhook/poller.",
                )
            if order.status == OrderStatus.PROCESSING:
                order_services.transition_order(
                    order=order,
                    new_status=OrderStatus.SHIPPED,
                    notes="Moved to shipped from shipping webhook/poller.",
                )
                order.shipped_at = shipment.shipped_at or timezone.now()
                order.tracking_number = shipment.awb_code
                order.shipping_carrier = shipment.courier_name
                order.save(update_fields=["shipped_at", "tracking_number", "shipping_carrier", "updated_at"])
        elif target_order_status == OrderStatus.DELIVERED:
            if order.status == OrderStatus.PAID:
                order_services.transition_order(
                    order=order,
                    new_status=OrderStatus.PROCESSING,
                    notes="Moved to processing before delivered sync.",
                )
            if order.status == OrderStatus.PROCESSING:
                order_services.transition_order(
                    order=order,
                    new_status=OrderStatus.SHIPPED,
                    notes="Moved to shipped before delivered sync.",
                )
            if order.status == OrderStatus.SHIPPED:
                order_services.transition_order(
                    order=order,
                    new_status=OrderStatus.DELIVERED,
                    notes="Moved to delivered from shipping webhook/poller.",
                )
                order.delivered_at = shipment.delivered_at or timezone.now()
                order.save(update_fields=["delivered_at", "updated_at"])
        elif target_order_status == OrderStatus.CANCELLED and order.is_cancellable:
            order_services.cancel_order(order=order, reason="Shipping provider marked shipment cancelled.")
    except Exception as exc:
        logger.warning(
            "shipment_order_status_update_failed",
            order_id=str(order.id),
            shipment_id=str(shipment.id),
            target_status=target_order_status,
            error=str(exc),
        )


def process_webhook_event(event_id: str) -> ShipmentEvent:
    event = ShipmentEvent.objects.select_related("shipment", "shipment__order").get(id=event_id)
    payload = event.event_payload or {}

    provider_status = str(payload.get("current_status") or payload.get("shipment_status") or payload.get("status") or "")
    awb = str(payload.get("awb") or payload.get("awb_code") or "")
    shipment_id = str(payload.get("shipment_id") or payload.get("shipments_id") or "")

    shipment = None
    if event.shipment_id:
        shipment = event.shipment
    elif shipment_id:
        shipment = Shipment.objects.filter(external_shipment_id=shipment_id).first()
    elif awb:
        shipment = Shipment.objects.filter(awb_code=awb).first()

    if not shipment:
        event.provider_status = provider_status
        event.internal_status = ""
        event.save(update_fields=["provider_status", "internal_status"])
        return event

    provider = resolve_provider_for_shipment(shipment)
    new_status = provider.normalize_status(payload)
    shipment.status = new_status
    shipment.raw_provider_response = payload
    if new_status == ShipmentStatus.DELIVERED and not shipment.delivered_at:
        shipment.delivered_at = timezone.now()
    if new_status in {ShipmentStatus.PICKED_UP, ShipmentStatus.IN_TRANSIT, ShipmentStatus.OUT_FOR_DELIVERY} and not shipment.shipped_at:
        shipment.shipped_at = timezone.now()
    shipment.save()

    event.shipment = shipment
    event.provider_status = provider_status
    event.internal_status = new_status
    event.save(update_fields=["shipment", "provider_status", "internal_status"])

    _update_order_for_shipment_status(shipment, source=ShipmentEventSource.WEBHOOK)
    _set_order_shipping_fields(shipment.order, shipment)
    return event


@transaction.atomic
def cancel_shipment(*, shipment_id: str, changed_by=None) -> Shipment:
    shipment = Shipment.objects.select_for_update().select_related("order").get(id=shipment_id)
    provider = resolve_provider_for_shipment(shipment)
    result = provider.cancel_shipment(shipment)
    if not result.success:
        raise ShippingError(result.error_message or "Cancel shipment failed", code=result.error_code)

    shipment.status = ShipmentStatus.CANCELLED
    shipment.raw_provider_response = result.data.get("raw") or result.data
    shipment.save(update_fields=["status", "raw_provider_response", "updated_at"])

    _create_event(
        shipment=shipment,
        source=ShipmentEventSource.MANUAL,
        provider_status="cancelled",
        internal_status=ShipmentStatus.CANCELLED,
        payload=result.data,
    )

    if shipment.order.is_cancellable:
        order_services.cancel_order(order=shipment.order, changed_by=changed_by, reason="Shipment cancelled from logistics admin action.")

    return shipment


def list_shipments(*, status: str | None = None, provider: str | None = None):
    qs = Shipment.objects.select_related("order", "order__user").prefetch_related("events").order_by("-created_at")
    if status:
        qs = qs.filter(status=status)
    if provider:
        qs = qs.filter(provider=provider)
    return qs


def get_shipment_for_order(order_id: str) -> Shipment | None:
    return Shipment.objects.filter(order_id=order_id).first()


def create_webhook_event(*, payload: dict, idempotency_key: str, provider_name: str = "") -> ShipmentEvent:
    provider_status = str(payload.get("current_status") or payload.get("shipment_status") or payload.get("status") or "")
    event_payload = dict(payload or {})
    if provider_name:
        event_payload["_provider"] = provider_name
    return _create_event(
        shipment=None,
        source=ShipmentEventSource.WEBHOOK,
        provider_status=provider_status,
        internal_status="",
        payload=event_payload,
        idempotency_key=idempotency_key,
    )


def reconcile_stuck_shipments() -> int:
    cfg = get_provider_config()
    if not cfg.get("enabled", False):
        return 0

    active_statuses = [
        ShipmentStatus.CREATED,
        ShipmentStatus.AWB_ASSIGNED,
        ShipmentStatus.PICKUP_REQUESTED,
        ShipmentStatus.PICKED_UP,
        ShipmentStatus.IN_TRANSIT,
        ShipmentStatus.OUT_FOR_DELIVERY,
    ]
    queryset = Shipment.objects.filter(status__in=active_statuses).order_by("created_at")[:200]
    processed = 0
    for shipment in queryset:
        try:
            sync_tracking(shipment_id=str(shipment.id), source=ShipmentEventSource.POLLER)
            processed += 1
        except Exception as exc:
            logger.warning("shipment_reconcile_failed", shipment_id=str(shipment.id), error=str(exc))
    return processed


def refresh_provider_token() -> bool:
    name = get_active_provider_name()
    if not name:
        return False
    provider = registry.get(name)
    if hasattr(provider, "refresh_token"):
        result = provider.refresh_token()
        return bool(result.success)
    return False


def log_manual_action(*, user, action: str, shipment: Shipment, metadata: dict | None = None, request=None):
    actor_type = ActorType.ADMIN if getattr(user, "role", "") == "admin" else ActorType.STAFF
    log_activity(
        user=user,
        actor_type=actor_type,
        action=AuditAction.UPDATE,
        entity_type="shipment",
        entity_id=str(shipment.id),
        description=action,
        metadata=metadata or {},
        request=request,
    )
