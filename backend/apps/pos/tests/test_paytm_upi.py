"""
UPI at the counter on the shop's Paytm merchant account.

What must hold:
  - the QR (when there is one) is for the balance, never the total
  - nothing turns a sale paid except a staff confirmation with a UPI reference
  - a full UPI reference can't be booked against two sales
  - cash + Paytm UPI split settles the order
  - a voided sale with a Paytm leg tells staff how much UPI to refund
"""

from decimal import Decimal
from urllib.parse import unquote

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User, UserRole
from apps.features.models import AppSetting
from apps.orders.models import Order, OrderStatus, PaymentStatus, SalesChannel
from apps.payments.models import PaymentTransaction, TenderMethod, TenderStatus
from apps.pos import collection_service, services
from apps.pos.models import POSTerminal


def set_setting(key, value):
    AppSetting.objects.update_or_create(key=key, defaults={"value": value, "value_type": "string"})


class PaytmUpiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.staff = User.objects.create_user(
            email="priya@aurorablings.com", password="x", first_name="P", last_name="S",
            role=UserRole.STAFF,
        )
        self.terminal = POSTerminal.objects.create(code="SHOP-01", name="Shop")
        self.shift = services.open_shift(terminal=self.terminal, staff=self.staff)
        self.order = self._order()

    def _order(self, total="4798.00"):
        return Order.objects.create(
            status=OrderStatus.PLACED, payment_status=PaymentStatus.PENDING,
            subtotal=Decimal(total), grand_total=Decimal(total),
            channel=SalesChannel.POS, pos_shift=self.shift, pos_terminal=self.terminal,
        )

    # ── Which rail ────────────────────────────────────────────

    def test_paytm_is_the_default_counter_rail(self):
        self.assertEqual(collection_service.counter_upi_provider(), "paytm")

    def test_razorpay_is_still_selectable(self):
        set_setting("pos_upi_provider", "razorpay")
        self.assertEqual(collection_service.counter_upi_provider(), "razorpay")

    # ── The code on screen ────────────────────────────────────

    def test_qr_carries_the_balance_not_the_total(self):
        set_setting("pos_upi_vpa", "paytmqr1234@paytm")
        services.take_cash_tender(
            order=self.order, shift=self.shift, staff=self.staff,
            amount_applied=Decimal("2000.00"),
        )

        result = collection_service.create_upi_collection(
            order=self.order, staff=self.staff, shift=self.shift,
        )

        self.assertEqual(result["kind"], "upi_intent")
        self.assertEqual(result["amount"], "2798.00")
        self.assertTrue(result["requires_confirmation"])
        self.assertTrue(result["image_url"].startswith("data:image/svg+xml;base64,"))
        uri = unquote(result["upi_uri"])
        self.assertIn("pa=paytmqr1234@paytm", uri)
        self.assertIn("am=2798.00", uri)
        self.assertIn(f"tn={self.order.order_number}", uri)
        # Nothing was raised upstream, so there is no gateway attempt to log.
        self.assertFalse(PaymentTransaction.objects.filter(order=self.order).exists())

    def test_without_a_upi_id_staff_are_sent_to_the_standee(self):
        result = collection_service.create_upi_collection(order=self.order, staff=self.staff)
        self.assertEqual(result["kind"], "device")
        self.assertEqual(result["image_url"], "")
        self.assertEqual(result["amount"], "4798.00")

    def test_showing_a_qr_does_not_pay_anything(self):
        set_setting("pos_upi_vpa", "paytmqr1234@paytm")
        collection_service.create_upi_collection(order=self.order, staff=self.staff)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, PaymentStatus.PENDING)

    def test_paid_order_cannot_raise_another_code(self):
        services.take_upi_tender(order=self.order, shift=self.shift, staff=self.staff, reference="1234")
        with self.assertRaises(collection_service.CollectionError):
            collection_service.create_upi_collection(order=self.order, staff=self.staff)

    # ── Staff confirmation ───────────────────────────────────

    def test_confirmation_settles_the_whole_balance(self):
        tender = services.take_upi_tender(
            order=self.order, shift=self.shift, staff=self.staff, reference="412345678901",
        )
        self.order.refresh_from_db()

        self.assertEqual(tender.method, TenderMethod.UPI)
        self.assertEqual(tender.provider, "paytm")
        self.assertEqual(tender.provider_ref, "")
        self.assertEqual(tender.amount_applied, Decimal("4798.00"))
        self.assertEqual(tender.raw["upi_reference"], "412345678901")
        self.assertEqual(self.order.payment_status, PaymentStatus.PAID)
        self.assertEqual(self.order.payment_reference, "PAYTM-UPI-412345678901")

    def test_split_cash_then_paytm_upi(self):
        services.take_cash_tender(
            order=self.order, shift=self.shift, staff=self.staff,
            amount_applied=Decimal("2000.00"), cash_received=Decimal("2000.00"),
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, PaymentStatus.PARTIALLY_PAID)

        tender = services.take_upi_tender(
            order=self.order, shift=self.shift, staff=self.staff, reference="5678",
        )
        self.order.refresh_from_db()

        self.assertEqual(tender.amount_applied, Decimal("2798.00"))
        self.assertEqual(self.order.payment_status, PaymentStatus.PAID)
        # UPI is not drawer cash.
        self.assertEqual(services.cash_taken(self.shift), Decimal("2000.00"))

    def test_reference_is_required(self):
        for ref in ("", "  ", "12", "--1-"):
            with self.assertRaises(services.ShiftError):
                services.take_upi_tender(order=self.order, shift=self.shift, staff=self.staff, reference=ref)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, PaymentStatus.PENDING)

    def test_full_reference_cannot_be_used_twice(self):
        services.take_upi_tender(order=self.order, shift=self.shift, staff=self.staff, reference="412345678901")
        other = self._order("500.00")
        with self.assertRaises(services.ShiftError) as ctx:
            services.take_upi_tender(order=other, shift=self.shift, staff=self.staff, reference="4123 4567 8901")
        self.assertIn(self.order.order_number, str(ctx.exception))

    def test_last_four_digits_may_repeat(self):
        services.take_upi_tender(order=self.order, shift=self.shift, staff=self.staff, reference="8901")
        other = self._order("500.00")
        tender = services.take_upi_tender(order=other, shift=self.shift, staff=self.staff, reference="8901")
        self.assertEqual(tender.order_id, other.id)

    def test_closed_shift_refuses(self):
        services.close_shift(shift=self.shift, staff=self.staff, counted_cash=Decimal("0"), force=True)
        self.shift.refresh_from_db()
        with self.assertRaises(services.ShiftError):
            services.take_upi_tender(order=self.order, shift=self.shift, staff=self.staff, reference="1234")

    # ── Void and close ───────────────────────────────────────

    def test_void_part_paid_paytm_sale(self):
        order = self._order("1000.00")
        # A UPI leg on an order whose total later rises is the realistic part-paid
        # Paytm case; build it directly through the ledger.
        services.take_upi_tender(order=order, shift=self.shift, staff=self.staff, reference="1111")
        order.grand_total = Decimal("1500.00")
        order.save(update_fields=["grand_total"])
        from apps.payments import tender_service
        tender_service.sync_payment_status(order=order)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, PaymentStatus.PARTIALLY_PAID)

        voided = services.void_sale(order=order, staff=self.staff, reason="customer left")

        self.assertEqual(voided.paytm_upi_to_refund, Decimal("1000.00"))
        self.assertFalse(order.tenders.filter(status=TenderStatus.CAPTURED).exists())

    def test_shift_summary_lists_paytm_references(self):
        services.take_upi_tender(order=self.order, shift=self.shift, staff=self.staff, reference="412345678901")
        summary = services.shift_summary(self.shift)
        self.assertEqual(len(summary["paytm_upi"]), 1)
        self.assertEqual(summary["paytm_upi"][0]["reference"], "412345678901")
        self.assertEqual(summary["paytm_upi"][0]["amount"], "4798.00")
        self.assertEqual(summary["by_tender"]["upi"]["total"], "4798.00")


class PaytmUpiApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.staff = User.objects.create_user(
            email="priya@aurorablings.com", password="x", first_name="P", last_name="S",
            role=UserRole.STAFF,
        )
        self.terminal = POSTerminal.objects.create(code="SHOP-01", name="Shop")
        self.shift = services.open_shift(terminal=self.terminal, staff=self.staff)
        self.order = Order.objects.create(
            status=OrderStatus.PLACED, payment_status=PaymentStatus.PENDING,
            subtotal=Decimal("799.00"), grand_total=Decimal("799.00"),
            channel=SalesChannel.POS, pos_shift=self.shift, pos_terminal=self.terminal,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.staff)

    def test_upi_endpoint_returns_a_paytm_collection(self):
        response = self.client.post(
            reverse("pos:upi-collection", args=[self.order.id]),
            {"shift": str(self.shift.id)}, format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["provider"], "paytm")
        self.assertEqual(response.data["kind"], "device")

    def test_confirm_endpoint(self):
        url = reverse("pos:upi-tender", args=[self.shift.id])

        bad = self.client.post(url, {"order": str(self.order.id), "reference": "1"}, format="json")
        self.assertEqual(bad.status_code, 409)

        ok = self.client.post(url, {"order": str(self.order.id), "reference": "9876"}, format="json")
        self.assertEqual(ok.status_code, 201)
        self.assertEqual(ok.data["order_payment_status"], PaymentStatus.PAID)
        self.assertEqual(ok.data["balance_due"], "0.00")

        state = self.client.get(reverse("pos:payment-state", args=[self.order.id]))
        self.assertEqual(state.data["upi_provider"], "paytm")
        self.assertEqual(state.data["tenders"][0]["reference"], "9876")

    def test_customers_cannot_confirm_upi(self):
        customer = User.objects.create_user(email="c@example.com", password="x", first_name="C", last_name="C")
        client = APIClient()
        client.force_authenticate(customer)
        response = client.post(
            reverse("pos:upi-tender", args=[self.shift.id]),
            {"order": str(self.order.id), "reference": "9876"}, format="json",
        )
        self.assertEqual(response.status_code, 403)
