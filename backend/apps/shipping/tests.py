from __future__ import annotations

from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.features.models import AppSetting
from apps.orders.models import Order, OrderStatus, PaymentStatus, PaymentMethod
from apps.shipping import services
from apps.shipping.models import Shipment, ShipmentEvent, ShipmentStatus, ShipmentEventSource
from apps.shipping.providers.base import ProviderResponse
from apps.shipping.providers.shiprocket import ShiprocketProvider


class _FakeProvider:
    name = "shiprocket"

    def authenticate(self):
        return ProviderResponse(success=True, data={"token": "x"})

    def create_order(self, order):
        return ProviderResponse(
            success=True,
            status=ShipmentStatus.CREATED,
            data={
                "external_order_id": order.order_number,
                "external_shipment_id": "9001",
                "raw": {"ok": True},
            },
        )

    def assign_awb(self, shipment):
        return ProviderResponse(
            success=True,
            status=ShipmentStatus.AWB_ASSIGNED,
            data={"awb_code": "AWB123", "courier_name": "BlueDart", "courier_company_id": "12", "raw": {}},
        )

    def generate_label(self, shipment):
        return ProviderResponse(success=True, data={"label_url": "https://label"})

    def generate_manifest(self, shipment):
        return ProviderResponse(success=True, data={"manifest_url": "https://manifest"})

    def request_pickup(self, shipment):
        return ProviderResponse(success=True, status=ShipmentStatus.PICKUP_REQUESTED, data={"raw": {}})

    def cancel_shipment(self, shipment):
        return ProviderResponse(success=True, status=ShipmentStatus.CANCELLED, data={"raw": {"cancelled": True}})

    def get_tracking(self, shipment):
        return ProviderResponse(
            success=True,
            status=ShipmentStatus.DELIVERED,
            data={"provider_status": "delivered", "tracking_url": "https://track", "event": {}, "raw": {}},
        )

    def verify_serviceability(self, order_or_address):
        return ProviderResponse(success=True, data={"raw": {}})

    def normalize_status(self, payload):
        status = str(payload.get("status") or payload.get("current_status") or "").lower()
        if "deliver" in status:
            return ShipmentStatus.DELIVERED
        if "cancel" in status:
            return ShipmentStatus.CANCELLED
        return ShipmentStatus.IN_TRANSIT


class ShippingIntegrationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.admin = User.objects.create_user(email="admin@example.com", password="x", role="admin", is_staff=True)
        self.client.force_authenticate(self.admin)
        self._seed_settings()

    def _seed_settings(self):
        AppSetting.objects.update_or_create(
            key="shipping.provider",
            defaults={
                "value_type": "json",
                "value": '{"active":"shiprocket","enabled":true,"auto_create_shipment":true,"auto_generate_awb":true,"auto_request_pickup":false}',
                "category": "shipping",
                "is_editable": True,
                "is_public": False,
            },
        )
        AppSetting.objects.update_or_create(
            key="shipping.shiprocket",
            defaults={
                "value_type": "json",
                "value": '{"enabled":true,"api_user_email":"ops@example.com","api_user_password":"secret","webhook_enabled":true,"webhook_secret":"hook-secret","default_payment_method_prepaid":"Prepaid","default_payment_method_cod":"COD"}',
                "category": "shipping",
                "is_editable": True,
                "is_public": False,
            },
        )

    def _build_paid_order(self, **shipping_address):
        address = {
            "full_name": "Alice",
            "line1": "12 Main Street",
            "city": "Bengaluru",
            "state": "Karnataka",
            "pincode": "560001",
            "country": "India",
            "phone": "9999999999",
        }
        address.update(shipping_address)
        return Order.objects.create(
            user=self.admin,
            status=OrderStatus.PAID,
            payment_status=PaymentStatus.PAID,
            payment_method=PaymentMethod.RAZORPAY,
            shipping_address=address,
            billing_address=address,
            subtotal="1000",
            shipping_cost="50",
            discount_amount="0",
            tax_amount="0",
            grand_total="1050",
        )

    @mock.patch("apps.shipping.services.resolve_provider", return_value=_FakeProvider())
    def test_provider_resolution_from_settings(self, _resolve):
        self.assertEqual(services.get_active_provider_name(), "shiprocket")
        shipment = services.create_or_update_shipment_for_order(order_id=str(self._build_paid_order().id))
        self.assertEqual(shipment.provider, "shiprocket")

    @mock.patch("apps.shipping.services.resolve_provider", return_value=_FakeProvider())
    def test_shipment_creation_only_for_eligible_orders(self, _resolve):
        order = self._build_paid_order()
        order.status = OrderStatus.PLACED
        order.save(update_fields=["status"])
        with self.assertRaises(Exception):
            services.create_or_update_shipment_for_order(order_id=str(order.id))

    @mock.patch("apps.shipping.services.resolve_provider", return_value=_FakeProvider())
    def test_duplicate_prevention_idempotency(self, _resolve):
        order = self._build_paid_order()
        first = services.create_or_update_shipment_for_order(order_id=str(order.id))
        second = services.create_or_update_shipment_for_order(order_id=str(order.id))
        self.assertEqual(first.id, second.id)
        self.assertEqual(Shipment.objects.filter(order=order).count(), 1)

    @mock.patch("apps.shipping.providers.shiprocket.requests.post")
    def test_token_caching_and_refresh(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"token": "abc"}
        mock_post.return_value.raise_for_status.return_value = None

        provider = ShiprocketProvider()
        first = provider.authenticate()
        second = provider.authenticate()
        self.assertTrue(first.success)
        self.assertTrue(second.success)
        self.assertEqual(mock_post.call_count, 1)

        provider.refresh_token()
        self.assertEqual(mock_post.call_count, 2)

    @mock.patch("apps.shipping.services.resolve_provider", return_value=_FakeProvider())
    def test_shiprocket_success_path_persists_fields(self, _resolve):
        order = self._build_paid_order()
        shipment = services.create_or_update_shipment_for_order(order_id=str(order.id))
        self.assertEqual(shipment.awb_code, "AWB123")
        self.assertEqual(shipment.status, ShipmentStatus.AWB_ASSIGNED)
        self.assertTrue(shipment.label_url)
        self.assertTrue(shipment.manifest_url)

    @mock.patch("apps.shipping.services.resolve_provider", return_value=_FakeProvider())
    def test_webhook_auth_validation(self, _resolve):
        response = self.client.post(
            "/api/v1/logistics/tracking-update/",
            data={"status": "delivered", "awb": "AWB123"},
            format="json",
            HTTP_X_API_KEY="wrong",
        )
        self.assertEqual(response.status_code, 403)

    @mock.patch("apps.shipping.services.resolve_provider", return_value=_FakeProvider())
    def test_webhook_status_mapping_and_order_status_update(self, _resolve):
        order = self._build_paid_order()
        shipment = services.create_or_update_shipment_for_order(order_id=str(order.id))
        event = services.create_webhook_event(
            payload={"status": "delivered", "awb": shipment.awb_code, "shipment_id": shipment.external_shipment_id},
            idempotency_key="evt-1",
        )
        services.process_webhook_event(str(event.id))
        shipment.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(shipment.status, ShipmentStatus.DELIVERED)
        self.assertEqual(order.status, OrderStatus.DELIVERED)

    @mock.patch("apps.shipping.tasks.retry_create_shipment.delay")
    def test_admin_manual_retry_action_endpoint(self, mock_delay):
        order = self._build_paid_order()
        response = self.client.post(f"/api/v1/logistics/orders/{order.id}/shipment/create/", data={"force": True}, format="json")
        self.assertEqual(response.status_code, 200)
        mock_delay.assert_called_once()

    def test_preflight_validation_endpoint(self):
        order = self._build_paid_order(phone="")
        response = self.client.get(f"/api/v1/logistics/orders/{order.id}/shipment/preflight/")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["data"]["ok"])

    @mock.patch("apps.shipping.services.resolve_provider", return_value=_FakeProvider())
    def test_cancel_shipment_flow(self, _resolve):
        order = self._build_paid_order()
        shipment = services.create_or_update_shipment_for_order(order_id=str(order.id))
        services.cancel_shipment(shipment_id=str(shipment.id), changed_by=self.admin)
        shipment.refresh_from_db()
        self.assertEqual(shipment.status, ShipmentStatus.CANCELLED)

    @mock.patch("apps.shipping.tasks.create_shipment_for_order.delay")
    def test_order_mark_paid_queues_shipment_task(self, mock_delay):
        order = Order.objects.create(
            user=self.admin,
            status=OrderStatus.PLACED,
            payment_status=PaymentStatus.PENDING,
            payment_method=PaymentMethod.RAZORPAY,
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
            subtotal="1000",
            shipping_cost="50",
            discount_amount="0",
            tax_amount="0",
            grand_total="1050",
        )
        from apps.orders.services import mark_paid

        mark_paid(order=order, payment_reference="pay_1", changed_by=self.admin)
        mock_delay.assert_called_once_with(str(order.id))
