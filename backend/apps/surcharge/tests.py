from __future__ import annotations

from decimal import Decimal
from unittest import mock

from django.test import TestCase

from apps.surcharge.services import SurchargeContext, _apply_shipping_rules


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

