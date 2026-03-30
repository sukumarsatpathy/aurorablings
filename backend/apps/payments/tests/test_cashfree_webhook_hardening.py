import hashlib
import hmac
import json
from decimal import Decimal
from unittest.mock import patch

from django.test import RequestFactory, TestCase, override_settings

from apps.orders.models import Order, OrderStatus, PaymentMethod, PaymentStatus
from apps.payments.models import PaymentTransaction, TransactionStatus, WebhookEvent
from apps.payments.webhooks.cashfree_webhook import cashfree_webhook, process_cashfree_webhook_payload


@override_settings(CASHFREE_SECRET_KEY="test-secret")
class CashfreeWebhookHardeningTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.order = Order.objects.create(
            status=OrderStatus.PLACED,
            payment_status=PaymentStatus.PENDING,
            payment_method=PaymentMethod.COD,
            shipping_address={"line1": "x"},
            billing_address={"line1": "x"},
            subtotal=Decimal("100.00"),
            grand_total=Decimal("100.00"),
        )
        self.txn = PaymentTransaction.objects.create(
            order=self.order,
            provider="cashfree",
            provider_ref="cf-payment-xyz",
            status=TransactionStatus.PENDING,
            total_amount=Decimal("100.00"),
            refunded_amount=Decimal("0.00"),
            amount=Decimal("100.00"),
            currency="INR",
            raw_response={},
        )

    def _signature(self, payload: bytes) -> str:
        return hmac.new(b"test-secret", payload, hashlib.sha256).hexdigest()

    def test_invalid_signature_returns_403(self):
        payload = b'{"data":{"payment":{"cf_payment_id":"cf-payment-xyz","payment_status":"SUCCESS"}}}'
        request = self.factory.post(
            "/api/v1/payments/webhook/cashfree/",
            data=payload,
            content_type="application/json",
            HTTP_X_WEBHOOK_SIGNATURE="bad-signature",
        )
        response = cashfree_webhook(request)
        self.assertEqual(response.status_code, 403)

    def test_malformed_payload_returns_400(self):
        payload = b"{bad-json"
        request = self.factory.post(
            "/api/v1/payments/webhook/cashfree/",
            data=payload,
            content_type="application/json",
            HTTP_X_WEBHOOK_SIGNATURE=self._signature(payload),
        )
        response = cashfree_webhook(request)
        self.assertEqual(response.status_code, 400)

    def test_duplicate_event_is_idempotent(self):
        payload = {
            "event_id": "evt-dup-1",
            "data": {
                "payment": {
                    "order_id": str(self.order.id),
                    "cf_payment_id": "cf-payment-xyz",
                    "payment_status": "SUCCESS",
                }
            },
        }
        payload_bytes = json.dumps(payload).encode("utf-8")
        first = process_cashfree_webhook_payload(payload=payload, payload_bytes=payload_bytes)
        second = process_cashfree_webhook_payload(payload=payload, payload_bytes=payload_bytes)

        self.assertFalse(first["duplicate"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(WebhookEvent.objects.filter(event_id="evt-dup-1").count(), 1)

        self.txn.refresh_from_db()
        self.assertEqual(self.txn.status, TransactionStatus.SUCCESS)

    @patch("apps.payments.webhooks.cashfree_webhook.MAX_WEBHOOK_PAYLOAD_BYTES", 10)
    def test_payload_size_limit(self):
        payload = b'{"data":{"payment":{"payment_status":"SUCCESS"}}}'
        request = self.factory.post(
            "/api/v1/payments/webhook/cashfree/",
            data=payload,
            content_type="application/json",
            HTTP_X_WEBHOOK_SIGNATURE=self._signature(payload),
        )
        response = cashfree_webhook(request)
        self.assertEqual(response.status_code, 400)

