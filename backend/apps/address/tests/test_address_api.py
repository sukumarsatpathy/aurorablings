from __future__ import annotations

from unittest import mock

import requests
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.address.services.address_service import AddressService


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "address-tests",
        }
    }
)
class AddressApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.service = AddressService()

    @mock.patch("apps.address.services.address_service.requests.get")
    def test_valid_pincode_lookup(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.raise_for_status.return_value = None
        mock_get.return_value.json.return_value = [
            {
                "Status": "Success",
                "PostOffice": [
                    {"Name": "Bhubaneswar G.P.O", "District": "Bhubaneswar", "State": "Odisha"},
                    {"Name": "Ashok Nagar", "District": "Bhubaneswar", "State": "Odisha"},
                ],
            }
        ]

        response = self.client.get("/api/address/pincode/751001/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["city"], "Bhubaneswar")
        self.assertEqual(response.data["data"]["state"], "Odisha")
        self.assertEqual(response.data["data"]["area"], "Bhubaneswar G.P.O")
        self.assertEqual(response.data["data"]["areas"], ["Bhubaneswar G.P.O", "Ashok Nagar"])

    @mock.patch("apps.address.services.address_service.requests.get")
    def test_pincode_prefers_region_for_city(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.raise_for_status.return_value = None
        mock_get.return_value.json.return_value = [
            {
                "Status": "Success",
                "PostOffice": [
                    {
                        "Name": "Nandankanan",
                        "Region": "Bhubaneswar",
                        "District": "Khorda",
                        "Division": "Bhubaneswar Division",
                        "State": "Odisha",
                        "Pincode": "751034",
                    }
                ],
            }
        ]

        response = self.client.get("/api/address/pincode/751034/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["city"], "Bhubaneswar")
        self.assertEqual(response.data["data"]["state"], "Odisha")
        self.assertEqual(response.data["data"]["area"], "Nandankanan")
        self.assertEqual(response.data["data"]["pincode"], "751034")

    def test_invalid_pincode_returns_400(self):
        response = self.client.get("/api/address/pincode/75100/")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data["success"])

    @mock.patch("apps.address.services.address_service.requests.get")
    def test_cache_hit_avoids_second_external_call(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.raise_for_status.return_value = None
        mock_get.return_value.json.return_value = [
            {
                "Status": "Success",
                "PostOffice": [
                    {"Name": "Area 1", "District": "City X", "State": "State Y"},
                ],
            }
        ]

        first = self.service.get_from_pincode("560001")
        second = self.service.get_from_pincode("560001")
        self.assertEqual(first["city"], "City X")
        self.assertEqual(second["city"], "City X")
        self.assertEqual(mock_get.call_count, 1)

    @mock.patch("apps.address.services.address_service.requests.get")
    def test_api_failure_fallback(self, mock_get):
        mock_get.side_effect = requests.Timeout("timeout")
        response = self.client.get("/api/address/pincode/560001/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["city"], "")
        self.assertEqual(response.data["data"]["state"], "")
        self.assertEqual(response.data["data"]["area"], "")

    @mock.patch("apps.address.services.address_service.requests.get")
    def test_reverse_geocoding_lookup(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.raise_for_status.return_value = None
        mock_get.return_value.json.return_value = {
            "address": {
                "city": "Bhubaneswar",
                "state": "Odisha",
                "suburb": "Nayapalli",
                "postcode": "751024",
            }
        }

        response = self.client.post("/api/address/reverse/", data={"lat": 20.2961, "lng": 85.8245}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["city"], "Bhubaneswar")
        self.assertEqual(response.data["data"]["state"], "Odisha")
        self.assertEqual(response.data["data"]["area"], "Nayapalli")
        self.assertEqual(response.data["data"]["pincode"], "751024")

    @mock.patch("apps.address.api.views.lookup_by_pincode")
    def test_rate_limit_blocks_after_50_per_minute(self, mock_lookup):
        mock_lookup.return_value = {"city": "City", "state": "State", "area": "Area", "areas": ["Area"], "pincode": "751001"}
        for _ in range(50):
            response = self.client.get("/api/address/pincode/751001/")
            self.assertEqual(response.status_code, 200)

        blocked = self.client.get("/api/address/pincode/751001/")
        self.assertEqual(blocked.status_code, 403)
