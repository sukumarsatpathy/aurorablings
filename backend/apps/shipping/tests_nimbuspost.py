"""
NimbusPost, against its published API (users/login → Bearer token, then
courier/serviceability, shipments, shipments/track, shipments/cancel).

HTTP is mocked; these pin down what we send and how we read the answers.
"""
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.shipping import delivery_estimate as de
from apps.shipping.models import ShipmentStatus
from apps.shipping.providers import nimbuspost as np_mod
from apps.shipping.providers.nimbuspost import NimbusPostProvider

CFG = {
    "shipping.nimbuspost": {
        "pickup_pincode": "752002", "warehouse_name": "Puri Shop", "pickup_name": "Aurora Blings",
        "pickup_address": "Gangamata Bagicha", "pickup_city": "Puri", "pickup_state": "Odisha",
        "pickup_phone": "+91 78470 90866",
    },
    "shipping.provider": {"default_package": {"weight_kg": 0.3, "length_cm": 12, "breadth_cm": 12, "height_cm": 4}},
}


def settings_getter(values):
    return lambda key, default=None: values.get(key, default)


def http(status=200, body=None):
    response = mock.Mock(status_code=status)
    response.content = b"x"
    response.json.return_value = body if body is not None else {}
    return response


LOGIN_OK = http(body={"status": True, "data": "jwt-token"})
COURIERS = {"status": True, "data": [
    {"id": "8", "name": "DTDC Air", "total_charges": 101.48},
    {"id": "14", "name": "Xpressbees Surface", "total_charges": 106.2},
]}


@override_settings(NIMBUSPOST_EMAIL="ops@aurorablings.com", NIMBUSPOST_PASSWORD="secret")
class NimbusPostProviderTests(TestCase):
    def setUp(self):
        cache.clear()
        patcher = mock.patch.object(np_mod.feature_services, "get_setting", settings_getter(CFG))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.provider = NimbusPostProvider()

    @mock.patch.object(np_mod.requests, "request")
    @mock.patch.object(np_mod.requests, "post", return_value=LOGIN_OK)
    def test_logs_in_once_and_sends_bearer_token(self, login, call):
        call.return_value = http(body=COURIERS)
        self.provider.check_serviceability(destination="760010")
        self.provider.check_serviceability(destination="751001")
        self.assertEqual(login.call_count, 1)  # token cached
        self.assertEqual(login.call_args.kwargs["json"], {"email": "ops@aurorablings.com", "password": "secret"})
        headers = call.call_args.kwargs["headers"]
        self.assertEqual(headers["Authorization"], "Bearer jwt-token")
        self.assertTrue(call.call_args.kwargs["url"].endswith("/courier/serviceability"))
        self.assertEqual(call.call_args.kwargs["json"]["origin"], "752002")
        self.assertEqual(call.call_args.kwargs["json"]["payment_type"], "prepaid")

    @mock.patch.object(np_mod.requests, "request")
    @mock.patch.object(np_mod.requests, "post", return_value=LOGIN_OK)
    def test_expired_token_triggers_one_relogin(self, login, call):
        call.side_effect = [http(401, {"status": False, "message": "Invalid token"}), http(body=COURIERS)]
        result = self.provider.check_serviceability(destination="760010")
        self.assertTrue(result.success)
        self.assertEqual(login.call_count, 2)

    @mock.patch.object(np_mod.requests, "post", return_value=http(body={"status": False, "message": "Invalid email or password"}))
    def test_bad_login_is_reported(self, _login):
        result = self.provider.check_serviceability(destination="760010")
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "auth_failed")
        self.assertIn("Invalid email", result.error_message)

    @override_settings(NIMBUSPOST_PASSWORD="")
    def test_not_configured_without_password(self):
        self.assertFalse(self.provider.is_configured())

    @mock.patch.object(np_mod.requests, "request")
    @mock.patch.object(np_mod.requests, "post", return_value=LOGIN_OK)
    def test_serviceable_without_days(self, _login, call):
        call.return_value = http(body=COURIERS)
        data = self.provider.check_serviceability(destination="760010").data
        self.assertTrue(data["serviceable"])
        self.assertIsNone(data["days"])
        self.assertEqual([c["name"] for c in data["couriers"]], ["DTDC Air", "Xpressbees Surface"])

    @mock.patch.object(np_mod.requests, "request")
    @mock.patch.object(np_mod.requests, "post", return_value=LOGIN_OK)
    def test_delivery_days_are_used_when_present(self, _login, call):
        in_four = (timezone.localdate() + timedelta(days=4)).isoformat()
        call.return_value = http(body={"status": True, "data": [
            {"id": "8", "name": "DTDC Air", "edd": in_four},
            {"id": "6", "name": "Delhivery Surface", "estimated_delivery_days": "6"},
        ]})
        data = self.provider.check_serviceability(destination="760010").data
        self.assertEqual(data["days"], 4)

    @mock.patch.object(np_mod.requests, "request")
    @mock.patch.object(np_mod.requests, "post", return_value=LOGIN_OK)
    def test_not_serviceable(self, _login, call):
        for body in ({"status": True, "data": []},
                     {"status": False, "message": "Delivery pincode is not serviceable"}):
            cache.set(np_mod.TOKEN_CACHE_KEY, "jwt-token")
            call.return_value = http(body=body)
            result = self.provider.check_serviceability(destination="999999")
            self.assertTrue(result.success, body)
            self.assertFalse(result.data["serviceable"], body)

    @mock.patch.object(np_mod.requests, "request")
    @mock.patch.object(np_mod.requests, "post", return_value=LOGIN_OK)
    def test_outage_is_a_failure_not_unserviceable(self, _login, call):
        call.side_effect = np_mod.requests.Timeout("slow")
        result = self.provider.check_serviceability(destination="760010")
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "provider_temporary_failure")

    def _order(self, **overrides):
        item = SimpleNamespace(product_name="Laal Noor - Set of 2 Bangles", sku="LN-2", quantity=2,
                               unit_price=Decimal("399.00"), product_snapshot={"weight_grams": 120})
        values = dict(
            id="o1", order_number="3f2a9c1e-7b4d-4e8a-9c2f-1a2b3c4d5e6f", payment_method="razorpay",
            grand_total=Decimal("798.00"), shipping_cost=Decimal("0"), discount_amount=Decimal("0"),
            shipping_address={"full_name": "Asha", "line1": "12 MG Road", "line2": "", "city": "Berhampur",
                              "state": "Odisha", "pincode": "760010", "phone": "+91 98765 43210"},
            items=SimpleNamespace(all=lambda: [item]),
        )
        values.update(overrides)
        return SimpleNamespace(**values)

    @mock.patch.object(np_mod.requests, "request")
    @mock.patch.object(np_mod.requests, "post", return_value=LOGIN_OK)
    def test_create_shipment_payload_and_response(self, _login, call):
        call.return_value = http(body={"status": True, "data": {
            "order_id": 3351555, "shipment_id": 1929242, "awb_number": "59632220664",
            "courier_id": "5", "courier_name": "Bluedart", "status": "booked",
            "label": "https://nimbus-assets/label.pdf"}})
        result = self.provider.create_order(self._order())

        sent = call.call_args.kwargs["json"]
        self.assertTrue(call.call_args.kwargs["url"].endswith("/shipments"))
        self.assertLessEqual(len(sent["order_number"]), 20)
        self.assertEqual(sent["payment_type"], "prepaid")
        self.assertEqual(sent["consignee"]["phone"], "9876543210")
        self.assertEqual(sent["consignee"]["pincode"], "760010")
        self.assertEqual(sent["pickup"]["pincode"], "752002")
        self.assertEqual(sent["pickup"]["phone"], "7847090866")
        self.assertEqual(sent["package_weight"], 240)
        self.assertEqual(sent["order_items"][0], {"name": "Laal Noor - Set of 2 Bangles", "qty": "2", "price": "399.00", "sku": "LN-2"})

        self.assertTrue(result.success)
        self.assertEqual(result.status, ShipmentStatus.AWB_ASSIGNED)
        self.assertEqual(result.data["awb_code"], "59632220664")
        self.assertEqual(result.data["label_url"], "https://nimbus-assets/label.pdf")

    @mock.patch.object(np_mod.requests, "request")
    @mock.patch.object(np_mod.requests, "post", return_value=LOGIN_OK)
    def test_booking_rejection_returns_nimbus_message(self, _login, call):
        call.return_value = http(body={"status": False, "message": "Consignee name is required\n"})
        result = self.provider.create_order(self._order())
        self.assertFalse(result.success)
        self.assertIn("Consignee name", result.error_message)

    @mock.patch.object(np_mod.requests, "request")
    @mock.patch.object(np_mod.requests, "post", return_value=LOGIN_OK)
    def test_tracking_and_cancel(self, _login, call):
        shipment = SimpleNamespace(awb_code="59650109492", manifest_url="", label_url="")
        call.return_value = http(body={"status": True, "data": {"status": "delivered", "history": [
            {"status_code": "DL", "event_time": "2021-03-05 12:00", "message": "DELIVERED"}]}})
        self.assertEqual(self.provider.get_tracking(shipment).status, ShipmentStatus.DELIVERED)
        self.assertTrue(call.call_args.kwargs["url"].endswith("/shipments/track/59650109492"))

        call.return_value = http(body={"status": True, "data": {"status": "rto", "rto_status": "delivered", "history": []}})
        self.assertEqual(self.provider.get_tracking(shipment).status, ShipmentStatus.RETURNED)

        call.return_value = http(body={"status": True, "message": "Shipment Cancelled"})
        result = self.provider.cancel_shipment(shipment)
        self.assertEqual(result.status, ShipmentStatus.CANCELLED)
        self.assertEqual(call.call_args.kwargs["json"], {"awb": "59650109492"})

    def test_status_codes_map(self):
        for code, expected in [("PP", ShipmentStatus.PICKUP_REQUESTED), ("IT", ShipmentStatus.IN_TRANSIT),
                               ("OFD", ShipmentStatus.OUT_FOR_DELIVERY), ("DL", ShipmentStatus.DELIVERED),
                               ("RT-DL", ShipmentStatus.RETURNED), ("EX", ShipmentStatus.EXCEPTION)]:
            self.assertEqual(self.provider.normalize_status({"status_code": code}), expected, code)


@override_settings(NIMBUSPOST_EMAIL="ops@aurorablings.com", NIMBUSPOST_PASSWORD="secret")
class NimbusPostDeliveryEstimateTests(TestCase):
    """The product-page "Delivery by …" line, answered by NimbusPost."""

    TODAY = date(2026, 10, 21)

    def setUp(self):
        cache.clear()
        values = dict(CFG)
        values["shipping.delivery_estimate"] = {"min_days": 3, "max_days": 5, "dispatch_days": 1}
        for target in (np_mod.feature_services, de.feature_services):
            patcher = mock.patch.object(target, "get_setting", settings_getter(values))
            patcher.start()
            self.addCleanup(patcher.stop)
        lookup = mock.patch(
            "apps.address.services.address_service.AddressService.lookup_pincode",
            return_value=({"city": "Berhampur", "state": "Odisha"}, "ok"),
        )
        lookup.start()
        self.addCleanup(lookup.stop)

    def _estimate(self, live):
        with mock.patch.object(NimbusPostProvider, "check_serviceability", return_value=live):
            return de.estimate_delivery("760010", today=self.TODAY)

    def test_serviceable_uses_configured_range_when_no_days(self):
        result = self._estimate(np_mod.ProviderResponse(success=True, data={"serviceable": True, "days": None, "couriers": [{}]}))
        self.assertTrue(result["serviceable"])
        self.assertEqual(result["source"], "nimbuspost")
        self.assertEqual((result["earliest_date"], result["latest_date"]), ("2026-10-25", "2026-10-27"))
        self.assertEqual(result["city"], "Berhampur")

    def test_courier_days_win(self):
        result = self._estimate(np_mod.ProviderResponse(success=True, data={"serviceable": True, "days": 2, "couriers": [{}]}))
        self.assertEqual((result["min_days"], result["max_days"]), (3, 5))  # 2 + 1 dispatch, +2 spread

    def test_not_serviceable(self):
        result = self._estimate(np_mod.ProviderResponse(success=True, data={"serviceable": False, "days": None, "couriers": []}))
        self.assertFalse(result["serviceable"])
        self.assertEqual(result["source"], "nimbuspost")

    def test_nimbus_outage_falls_back_and_retries_soon(self):
        with mock.patch.object(de.cache, "set", wraps=de.cache.set) as cache_set:
            result = self._estimate(np_mod.ProviderResponse(success=False, error_code="provider_temporary_failure"))
        self.assertIsNone(result["serviceable"])
        self.assertEqual(result["source"], "configured")
        self.assertEqual(cache_set.call_args.kwargs["timeout"], de.FAILED_LOOKUP_CACHE_SECONDS)
