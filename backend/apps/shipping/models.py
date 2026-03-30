import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _


class ShipmentProvider(models.TextChoices):
    SHIPROCKET = "shiprocket", _("Shiprocket")


class ShipmentStatus(models.TextChoices):
    CREATED = "created", _("Created")
    AWB_ASSIGNED = "awb_assigned", _("AWB Assigned")
    PICKUP_REQUESTED = "pickup_requested", _("Pickup Requested")
    PICKED_UP = "picked_up", _("Picked Up")
    IN_TRANSIT = "in_transit", _("In Transit")
    OUT_FOR_DELIVERY = "out_for_delivery", _("Out for Delivery")
    DELIVERED = "delivered", _("Delivered")
    RTO = "rto", _("RTO")
    CANCELLED = "cancelled", _("Cancelled")
    FAILED = "failed", _("Failed")
    EXCEPTION = "exception", _("Exception")


class ShipmentEventSource(models.TextChoices):
    WEBHOOK = "webhook", _("Webhook")
    POLLER = "poller", _("Poller")
    MANUAL = "manual", _("Manual")
    SYSTEM = "system", _("System")


class Shipment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="shipment",
    )
    provider = models.CharField(max_length=50, choices=ShipmentProvider.choices, db_index=True)
    status = models.CharField(
        max_length=30,
        choices=ShipmentStatus.choices,
        default=ShipmentStatus.CREATED,
        db_index=True,
    )

    external_order_id = models.CharField(max_length=120, blank=True, db_index=True)
    external_shipment_id = models.CharField(max_length=120, blank=True, db_index=True)
    awb_code = models.CharField(max_length=120, blank=True, db_index=True)
    courier_name = models.CharField(max_length=120, blank=True)
    courier_company_id = models.CharField(max_length=120, blank=True)

    tracking_url = models.URLField(blank=True)
    label_url = models.URLField(blank=True)
    manifest_url = models.URLField(blank=True)
    invoice_url = models.URLField(blank=True)

    pickup_requested = models.BooleanField(default=False)
    pickup_scheduled_at = models.DateTimeField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    raw_provider_response = models.JSONField(default=dict, blank=True)
    error_code = models.CharField(max_length=120, blank=True)
    error_message = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["provider"]),
            models.Index(fields=["awb_code"]),
            models.Index(fields=["external_shipment_id"]),
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.order.order_number} / {self.provider} / {self.status}"


class ShipmentEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shipment = models.ForeignKey(
        Shipment,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="events",
    )
    source = models.CharField(max_length=20, choices=ShipmentEventSource.choices, db_index=True)
    provider_status = models.CharField(max_length=120, blank=True)
    internal_status = models.CharField(max_length=30, choices=ShipmentStatus.choices, blank=True)
    event_payload = models.JSONField(default=dict, blank=True)
    idempotency_key = models.CharField(max_length=255, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["idempotency_key"],
                condition=models.Q(idempotency_key__gt=""),
                name="shipping_unique_event_idempotency_key",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.source} / {self.provider_status or self.internal_status}"
