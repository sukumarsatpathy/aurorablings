"""
"Delivery by …" on the product page.

What matters: a bad pincode is rejected, a pincode no courier serves is said
so, Shiprocket's answer wins when it's available, and when it isn't the shop's
configured range is used instead of failing.
"""
from datetime import date
from unittest import mock

from django.core.cache import cache
from django.test import TestCase

from apps.shipping import delivery_estimate as de
from apps.shipping.providers.base import ProviderResponse
from apps.shipping.providers.shiprocket import ShiprocketProvider

TODAY = date(2026, 10, 19)
PURI = {"city": "Puri", "state": "Odisha", "area": "", "areas": [], "pincode": "752002"}


def _settings(values):
    return lambda key, default=None: values.get(key, default)


class DeliveryEstimateTests(TestCase):
    def setUp(self):
        cache.clear()
        self.lookup = mock.patch(
            "apps.address.services.address_service.AddressService.get_from_pincode", return_value=PURI,
        )
        self.lookup.start()
        self.addCleanup(self.lookup.stop)

    def test_malformed_pincode_is_rejected(self):
        for bad in ["", "12345", "1234567", "abcdef", "052002"]:
            with self.assertRaises(ValueError):
                de.estimate_delivery(bad, today=TODAY)

    @mock.patch("apps.shipping.services.get_active_provider_name", return_value="")
    def test_configured_range_when_no_live_provider(self, _p):
        with mock.patch.object(de.feature_services, "get_setting", _settings({
            "shipping.delivery_estimate": {"min_days": 3, "max_days": 6, "dispatch_days": 1},
        })):
            result = de.estimate_delivery("560001", today=TODAY)
        self.assertIsNone(result["serviceable"])
        self.assertEqual((result["min_days"], result["max_days"]), (4, 7))
        self.assertEqual(result["earliest_date"], "2026-10-23")
        self.assertEqual(result["latest_date"], "2026-10-26")
        self.assertEqual(result["city"], "Puri")
        self.assertEqual(result["source"], "configured")

    @mock.patch("apps.shipping.services.get_active_provider_name", return_value="")
    def test_default_range_without_any_config(self, _p):
        with mock.patch.object(de.feature_services, "get_setting", _settings({})):
            result = de.estimate_delivery("560001", today=TODAY)
        self.assertEqual((result["min_days"], result["max_days"]), (5, 8))  # 4–7 + 1 dispatch day

    @mock.patch("apps.shipping.services.get_active_provider_name", return_value="")
    def test_local_pincode_uses_local_range(self, _p):
        with mock.patch.object(de.feature_services, "get_setting", _settings({
            "shipping.delivery_estimate": {"local_pincodes": ["752002"], "local_min_days": 0, "local_max_days": 1},
        })):
            result = de.estimate_delivery("752002", today=TODAY)
        self.assertTrue(result["serviceable"])
        self.assertEqual((result["min_days"], result["max_days"]), (0, 1))
        self.assertEqual(result["source"], "local")

    @mock.patch("apps.shipping.services.get_active_provider_name", return_value="")
    def test_unknown_pincode_is_not_serviceable(self, _p):
        with mock.patch(
            "apps.address.services.address_service.AddressService.get_from_pincode",
            return_value={"city": "", "state": "", "area": "", "areas": [], "pincode": ""},
        ), mock.patch.object(de.feature_services, "get_setting", _settings({})):
            result = de.estimate_delivery("999999", today=TODAY)
        self.assertFalse(result["serviceable"])
        self.assertIsNone(result["earliest_date"])

    @mock.patch("apps.shipping.services.get_active_provider_name", return_value="shiprocket")
    def test_shiprocket_days_win(self, _p):
        live = ProviderResponse(success=True, data={"serviceable": True, "days": 3, "city": "", "state": ""})
        with mock.patch.object(ShiprocketProvider, "delivery_days_for_pincode", return_value=live), \
                mock.patch.object(de.feature_services, "get_setting", _settings({})):
            result = de.estimate_delivery("560001", today=TODAY)
        self.assertTrue(result["serviceable"])
        self.assertEqual((result["min_days"], result["max_days"]), (4, 6))
        self.assertEqual(result["source"], "shiprocket")

    @mock.patch("apps.shipping.services.get_active_provider_name", return_value="shiprocket")
    def test_shiprocket_not_serviceable(self, _p):
        live = ProviderResponse(success=True, data={"serviceable": False, "days": None, "city": "", "state": ""})
        with mock.patch.object(ShiprocketProvider, "delivery_days_for_pincode", return_value=live), \
                mock.patch.object(de.feature_services, "get_setting", _settings({})):
            result = de.estimate_delivery("560001", today=TODAY)
        self.assertFalse(result["serviceable"])

    @mock.patch("apps.shipping.services.get_active_provider_name", return_value="shiprocket")
    def test_shiprocket_outage_falls_back_to_configured_range(self, _p):
        down = ProviderResponse(success=False, error_code="provider_temporary_failure")
        with mock.patch.object(ShiprocketProvider, "delivery_days_for_pincode", return_value=down), \
                mock.patch.object(de.feature_services, "get_setting", _settings({})):
            result = de.estimate_delivery("560001", today=TODAY)
        self.assertIsNone(result["serviceable"])
        self.assertEqual(result["source"], "configured")

    @mock.patch("apps.shipping.services.get_active_provider_name", return_value="")
    def test_result_is_cached_per_pincode(self, _p):
        with mock.patch.object(de.feature_services, "get_setting", _settings({})), \
                mock.patch.object(de, "_compute", wraps=de._compute) as compute:
            de.estimate_delivery("560001", today=TODAY)
            de.estimate_delivery("560001", today=TODAY)
        self.assertEqual(compute.call_count, 1)

    @mock.patch("apps.shipping.services.get_active_provider_name", return_value="")
    def test_endpoint(self, _p):
        ok = self.client.get("/api/v1/logistics/delivery-estimate/?pincode=752002")
        bad = self.client.get("/api/v1/logistics/delivery-estimate/?pincode=12")
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.json()["data"]["pincode"], "752002")
        self.assertEqual(bad.status_code, 400)


class ShiprocketServiceabilityParsingTests(TestCase):
    def _provider(self, response):
        provider = ShiprocketProvider()
        patches = [
            mock.patch.object(ShiprocketProvider, "_settings", return_value={"pickup_pincode": "752002"}),
            mock.patch.object(ShiprocketProvider, "_provider_settings", return_value={}),
            mock.patch.object(ShiprocketProvider, "_request", return_value=response),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        return provider

    def test_recommended_courier_days(self):
        body = {"status": 200, "data": {"recommended_courier_company_id": 2, "available_courier_companies": [
            {"courier_company_id": 1, "estimated_delivery_days": "2", "city": "Bengaluru", "state": "Karnataka"},
            {"courier_company_id": 2, "estimated_delivery_days": "4", "city": "Bengaluru", "state": "Karnataka"},
        ]}}
        data = self._provider(ProviderResponse(success=True, data=body)).delivery_days_for_pincode("560001").data
        self.assertEqual(data, {"serviceable": True, "days": 4, "city": "Bengaluru", "state": "Karnataka"})

    def test_fastest_courier_when_no_recommendation(self):
        body = {"data": {"available_courier_companies": [
            {"courier_company_id": 1, "estimated_delivery_days": "5"},
            {"courier_company_id": 2, "estimated_delivery_days": "3"},
        ]}}
        data = self._provider(ProviderResponse(success=True, data=body)).delivery_days_for_pincode("560001").data
        self.assertEqual(data["days"], 3)

    def test_404_means_not_serviceable(self):
        result = self._provider(ProviderResponse(
            success=False, error_code="provider_temporary_failure", data={"status_code": 404},
        )).delivery_days_for_pincode("560001")
        self.assertTrue(result.success)
        self.assertFalse(result.data["serviceable"])

    def test_empty_courier_list_means_not_serviceable(self):
        body = {"status": 404, "message": "Delivery postcode not serviceable", "data": {}}
        data = self._provider(ProviderResponse(success=True, data=body)).delivery_days_for_pincode("560001").data
        self.assertFalse(data["serviceable"])
