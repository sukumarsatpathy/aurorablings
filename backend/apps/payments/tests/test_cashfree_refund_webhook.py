from decimal import Decimal

from django.test import TestCase

from apps.orders.models import Order, OrderStatus, PaymentMethod, PaymentStatus
from apps.payments.models import PaymentTransaction, Refund, TransactionStatus
from apps.payments.webhooks.cashfree_webhook import handle_refund_webhook


class CashfreeRefundWebhookTests(TestCase):
    def setUp(self):
        self.order = Order.objects.create(
            status=OrderStatus.PLACED,
            payment_status=PaymentStatus.PAID,
            payment_method=PaymentMethod.COD,
            shipping_address={"line1": "a"},
            billing_address={"line1": "a"},
            subtotal=Decimal("300.00"),
            grand_total=Decimal("300.00"),
        )
        self.payment = PaymentTransaction.objects.create(
            order=self.order,
            provider="cashfree",
            provider_ref="cf-payment-1",
            status=TransactionStatus.SUCCESS,
            total_amount=Decimal("300.00"),
            refunded_amount=Decimal("0.00"),
            amount=Decimal("300.00"),
            currency="INR",
            raw_response={},
        )

    def test_success_refund_webhook_applies_refund(self):
        refund = handle_refund_webhook(
            refund_data={
                "order_id": str(self.order.id),
                "cf_payment_id": "cf-payment-1",
                "refund_id": "RFND-WH-1",
                "cf_refund_id": "CFR-1",
                "refund_amount": "120.00",
                "refund_status": "SUCCESS",
            },
            provider_name="cashfree",
        )
        self.assertIsNotNone(refund)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.refunded_amount, Decimal("120.00"))
        self.assertEqual(self.payment.status, TransactionStatus.PARTIALLY_REFUNDED)

    def test_pending_refund_webhook_creates_pending_refund_without_amount_application(self):
        refund = handle_refund_webhook(
            refund_data={
                "order_id": str(self.order.id),
                "cf_payment_id": "cf-payment-1",
                "refund_id": "RFND-WH-PENDING-1",
                "refund_amount": "50.00",
                "refund_status": "PENDING",
            },
            provider_name="cashfree",
        )
        self.assertIsNotNone(refund)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.refunded_amount, Decimal("0.00"))
        self.assertEqual(refund.status, "initiated")

    def test_duplicate_webhook_retry_does_not_double_apply(self):
        payload = {
            "order_id": str(self.order.id),
            "cf_payment_id": "cf-payment-1",
            "refund_id": "RFND-WH-DUP-1",
            "cf_refund_id": "CFR-DUP-1",
            "refund_amount": "70.00",
            "refund_status": "SUCCESS",
        }
        handle_refund_webhook(refund_data=payload, provider_name="cashfree")
        handle_refund_webhook(refund_data=payload, provider_name="cashfree")
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.refunded_amount, Decimal("70.00"))
        self.assertEqual(Refund.objects.filter(refund_id="RFND-WH-DUP-1").count(), 1)

