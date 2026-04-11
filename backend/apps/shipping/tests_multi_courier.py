from __future__ import annotations

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.orders.models import (
    Order,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
    ShippingApprovalStatus,
    FulfillmentMethod,
)
from apps.shipping.models import ShipmentStatus, ShipmentEvent
from apps.shipping import services as shipping_services
from apps.shipping.providers.nimbuspost import NimbusPostProvider


class MultiCourierShippingTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(email="ops@example.com", password="x", role="admin", is_staff=True)
        self.customer = User.objects.create_user(email="customer@example.com", password="x", role="customer")
        self.order = Order.objects.create(
            user=self.customer,
            status=OrderStatus.PAID,
            payment_status=PaymentStatus.PAID,
            payment_method=PaymentMethod.RAZORPAY,
            shipping_approval_status=ShippingApprovalStatus.PENDING_SHIPPING_APPROVAL,
            fulfillment_method=FulfillmentMethod.UNASSIGNED,
            shipping_address={
                "full_name": "Alice",
                "line1": "12 Main Street",
                "city": "Bengaluru",
                "state": "Karnataka",
                "pincode": "560001",
                "country": "India",
                "phone": "9999999999",
            },
            billing_address={
                "full_name": "Alice",
                "line1": "12 Main Street",
                "city": "Bengaluru",
                "state": "Karnataka",
                "pincode": "560001",
                "country": "India",
                "phone": "9999999999",
            },
            subtotal="500",
            shipping_cost="50",
            discount_amount="0",
            tax_amount="0",
            grand_total="550",
        )

    def test_approve_shipping_local_delivery_flow(self):
        updated = shipping_services.approve_order_shipping(
            order_id=str(self.order.id),
            fulfillment_method=FulfillmentMethod.LOCAL_DELIVERY,
            approved_by=self.admin,
            notes="Local rider assigned",
            local_meta={"rider_name": "Ravi", "rider_phone": "9999999999", "local_status": "assigned"},
        )
        self.assertEqual(updated.shipping_approval_status, ShippingApprovalStatus.APPROVED)
        shipment = updated.shipment
        self.assertEqual(shipment.provider, "local_delivery")
        self.assertEqual(shipment.status, ShipmentStatus.APPROVED)
        self.assertEqual(shipment.local_rider_name, "Ravi")

    def test_local_delivery_shipment_creation_without_external_api(self):
        shipping_services.approve_order_shipping(
            order_id=str(self.order.id),
            fulfillment_method=FulfillmentMethod.LOCAL_DELIVERY,
            approved_by=self.admin,
            notes="Local",
            local_meta={"local_status": "assigned"},
        )
        shipment = shipping_services.create_or_update_shipment_for_order(order_id=str(self.order.id), force=True)
        self.assertEqual(shipment.provider, "local_delivery")
        self.assertEqual(shipment.status, ShipmentStatus.ASSIGNED)

    def test_nimbus_status_mapping(self):
        provider = NimbusPostProvider()
        self.assertEqual(provider.normalize_status({"status": "out_for_delivery"}), ShipmentStatus.OUT_FOR_DELIVERY)
        self.assertEqual(provider.normalize_status({"status": "delivered"}), ShipmentStatus.DELIVERED)
        self.assertEqual(provider.normalize_status({"status": "returned"}), ShipmentStatus.RETURNED)

    def test_webhook_idempotency_event(self):
        payload = {"status": "delivered", "awb": "AWB-1"}
        key = NimbusPostProvider.build_event_idempotency_key(payload)
        shipping_services.create_webhook_event(payload=payload, idempotency_key=key, provider_name="nimbuspost")
        shipping_services.create_webhook_event(payload=payload, idempotency_key=key, provider_name="nimbuspost")
        self.assertEqual(ShipmentEvent.objects.filter(idempotency_key=key).count(), 1)

    def test_customer_can_only_view_own_shipping_status(self):
        self.client.force_authenticate(self.customer)
        response = self.client.get(f"/api/v1/logistics/orders/{self.order.id}/shipping-status/")
        self.assertEqual(response.status_code, 200)

        stranger = User.objects.create_user(email="stranger@example.com", password="x", role="customer")
        self.client.force_authenticate(stranger)
        forbidden = self.client.get(f"/api/v1/logistics/orders/{self.order.id}/shipping-status/")
        self.assertEqual(forbidden.status_code, 404)
