"""
Raising a UPI collection at the counter.

The two things worth pinning: the QR is for the *balance*, and nothing short of a
verified webhook turns the till green.
"""

from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User, UserRole
from apps.orders.models import Order, OrderStatus, PaymentStatus, SalesChannel
from apps.payments.providers.base import PaymentResult, QRCodeResult
from apps.pos import collection_service, services
from apps.pos.models import POSTerminal


def qr_ok(**kwargs):
    return QRCodeResult(
        success=True, provider_ref="qr_TEST123",
        image_url="https://rzp.io/i/qr_TEST123.png",
        amount=kwargs.get("amount", Decimal("0")), close_by=1900000000, raw={"id": "qr_TEST123"},
    )


class CollectionTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            email="priya@aurorablings.com", password="x", first_name="P", last_name="S",
            role=UserRole.STAFF,
        )
        self.terminal = POSTerminal.objects.create(code="STALL-01", name="Stall")
        self.shift = services.open_shift(terminal=self.terminal, staff=self.staff)
        self.order = Order.objects.create(
            guest_email="walkin@example.com",
            status=OrderStatus.PLACED, payment_status=PaymentStatus.PENDING,
            subtotal=Decimal("4798.00"), grand_total=Decimal("4798.00"),
            channel=SalesChannel.POS, pos_shift=self.shift, pos_terminal=self.terminal,
        )

    @patch("apps.payments.providers.razorpay.RazorpayProvider.create_qr_code")
    def test_qr_is_raised_for_the_balance_not_the_total(self, mock_qr):
        """A split sale's second leg. Charging the full total here would take
        Rs 2,000 from a customer who has already handed it over in cash."""
        mock_qr.side_effect = lambda **kw: qr_ok(**kw)

        services.take_cash_tender(
            order=self.order, shift=self.shift, staff=self.staff,
            amount_applied=Decimal("2000.00"),
        )
        result = collection_service.create_upi_collection(order=self.order, staff=self.staff)

        self.assertEqual(result["kind"], "qr")
        self.assertEqual(result["amount"], "2798.00")
        self.assertEqual(mock_qr.call_args.kwargs["amount"], Decimal("2798.00"))

    @patch("apps.payments.providers.razorpay.RazorpayProvider.create_qr_code")
    def test_a_fully_paid_order_cannot_raise_another_qr(self, mock_qr):
        mock_qr.side_effect = lambda **kw: qr_ok(**kw)
        services.take_cash_tender(
            order=self.order, shift=self.shift, staff=self.staff,
            amount_applied=Decimal("4798.00"),
        )
        with self.assertRaises(collection_service.CollectionError):
            collection_service.create_upi_collection(order=self.order, staff=self.staff)

    @patch("apps.payments.providers.razorpay.RazorpayProvider.initiate")
    @patch("apps.payments.providers.razorpay.RazorpayProvider.create_qr_code")
    def test_falls_back_to_a_payment_link_when_qr_is_not_enabled(self, mock_qr, mock_link):
        """Razorpay does not enable the QR product on every account. A merchant
        without it should get a working till, not a dead button."""
        mock_qr.return_value = QRCodeResult(
            success=False, error="The requested URL was not found on this server.",
        )
        mock_link.return_value = PaymentResult(success=True, provider_ref="plink_TEST9")

        result = collection_service.create_upi_collection(order=self.order, staff=self.staff)

        self.assertEqual(result["kind"], "link")
        self.assertEqual(result["qr_id"], "plink_TEST9")
        self.assertIn("QR codes unavailable", result["note"])

    @patch("apps.payments.providers.razorpay.RazorpayProvider.initiate")
    @patch("apps.payments.providers.razorpay.RazorpayProvider.create_qr_code")
    def test_both_failing_is_an_error_not_a_silent_pending(self, mock_qr, mock_link):
        mock_qr.return_value = QRCodeResult(success=False, error="qr off")
        mock_link.return_value = PaymentResult(success=False, provider_ref="", error="keys missing")

        with self.assertRaises(collection_service.CollectionError) as ctx:
            collection_service.create_upi_collection(order=self.order, staff=self.staff)
        self.assertIn("keys missing", str(ctx.exception))


class PaymentStatePollingTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.staff = User.objects.create_user(
            email="priya@aurorablings.com", password="x", first_name="P", last_name="S",
            role=UserRole.STAFF,
        )
        self.client.force_authenticate(self.staff)
        self.order = Order.objects.create(
            guest_email="walkin@example.com",
            status=OrderStatus.PLACED, payment_status=PaymentStatus.PENDING,
            subtotal=Decimal("2500.00"), grand_total=Decimal("2500.00"),
            channel=SalesChannel.POS,
        )

    def test_polling_reports_pending_until_a_tender_exists(self):
        url = reverse("pos:payment-state", kwargs={"order_id": self.order.id})
        body = self.client.get(url).data

        self.assertEqual(body["payment_status"], PaymentStatus.PENDING)
        self.assertEqual(body["balance_due"], "2500.00")
        self.assertEqual(body["tenders"], [])

    def test_polling_turns_green_only_once_the_ledger_says_so(self):
        from apps.payments import tender_service
        from apps.payments.models import TenderMethod

        url = reverse("pos:payment-state", kwargs={"order_id": self.order.id})
        tender_service.record_tender(
            order=self.order, method=TenderMethod.UPI, amount_applied=Decimal("2500.00"),
            provider="razorpay", provider_ref="pay_POLLTEST01",
        )
        body = self.client.get(url).data

        self.assertEqual(body["payment_status"], PaymentStatus.PAID)
        self.assertEqual(body["balance_due"], "0.00")
        self.assertEqual(len(body["tenders"]), 1)
