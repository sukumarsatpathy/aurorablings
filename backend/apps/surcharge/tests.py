from __future__ import annotations

from decimal import Decimal
from unittest import mock

from django.test import TestCase

from apps.surcharge.models import ShippingMethod, ShippingRule
from apps.surcharge.services import SurchargeContext, _apply_shipping_rules, calculate_surcharges


class SurchargeFallbackTests(TestCase):
    def test_shipping_standard_fallback_applies_flat_rate(self):
        ctx = SurchargeContext(
            subtotal=Decimal("299.00"),
            items=[],
            payment_method="cod",
            state_code="Odisha",
            pincode="751024",
        )
        with mock.patch("apps.surcharge.services.feature_services.get_setting", return_value={"flat_rate": 100, "free_shipping_threshold": 799}):
            lines = _apply_shipping_rules(ctx)

        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0].amount, Decimal("100.00"))
        self.assertEqual(lines[0].rule_id, "setting:shipping.standard")

    def test_shipping_standard_fallback_applies_free_above_threshold(self):
        ctx = SurchargeContext(
            subtotal=Decimal("1200.00"),
            items=[],
            payment_method="cod",
            state_code="Odisha",
            pincode="751024",
        )
        with mock.patch("apps.surcharge.services.feature_services.get_setting", return_value={"flat_rate": 100, "free_shipping_threshold": 799}):
            lines = _apply_shipping_rules(ctx)

        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0].amount, Decimal("0.00"))



STANDARD = {"flat_rate": 100, "free_shipping_threshold": 799}


class FreeShippingThresholdTests(TestCase):
    """The storefront's "Add ₹X more for free delivery" depends on these."""

    def _ctx(self, subtotal: str) -> SurchargeContext:
        return SurchargeContext(subtotal=Decimal(subtotal), items=[], payment_method="cod", state_code="Odisha")

    def test_threshold_is_exposed_from_standard_setting(self):
        with mock.patch("apps.surcharge.services.feature_services.get_setting", return_value=STANDARD):
            result = calculate_surcharges(self._ctx("399.00")).as_dict()
        self.assertEqual(result["shipping_total"], "100.00")
        self.assertEqual(result["free_shipping_threshold"], "799.00")

    def test_threshold_is_exposed_from_free_threshold_rule(self):
        ShippingRule.objects.create(
            name="Standard", method=ShippingMethod.FREE_THRESHOLD,
            flat_rate=Decimal("80.00"), free_threshold_amount=Decimal("999.00"),
        )
        result = calculate_surcharges(self._ctx("399.00")).as_dict()
        self.assertEqual(result["shipping_total"], "80.00")
        self.assertEqual(result["free_shipping_threshold"], "999.00")

    def test_no_threshold_for_flat_rule(self):
        ShippingRule.objects.create(name="Flat", method=ShippingMethod.FLAT, flat_rate=Decimal("60.00"))
        result = calculate_surcharges(self._ctx("399.00")).as_dict()
        self.assertIsNone(result["free_shipping_threshold"])

    def test_shipping_summary_endpoint(self):
        with mock.patch("apps.surcharge.services.feature_services.get_setting", return_value=STANDARD):
            small = self.client.get("/api/v1/surcharge/shipping-summary/?subtotal=399").json()["data"]
            large = self.client.get("/api/v1/surcharge/shipping-summary/?subtotal=899").json()["data"]
            junk = self.client.get("/api/v1/surcharge/shipping-summary/?subtotal=abc")
        self.assertEqual(small["shipping_total"], "100.00")
        self.assertEqual(small["free_shipping_threshold"], "799.00")
        self.assertEqual(large["shipping_total"], "0.00")
        self.assertEqual(junk.status_code, 200)
