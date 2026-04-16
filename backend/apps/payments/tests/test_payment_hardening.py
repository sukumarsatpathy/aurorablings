"""
tests.test_payment_hardening
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Comprehensive tests for the hardened Cashfree payment flow.

Covers:
  - Amount & currency validation
  - Payment state machine guards
  - Webhook idempotency
  - Signature verification
  - Payment retry flow
  - Refund cap enforcement
  - Stock release on payment failure
  - Generic webhook endpoint hardening
  - Reconciliation amount validation
"""

import hashlib
import hmac
import json
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from apps.orders.models import Order, OrderStatus, PaymentMethod, PaymentStatus
from apps.payments.models import (
    PaymentTransaction,
    Refund,
    RefundSource,
    RefundStatus,
    TransactionStatus,
    WebhookEvent,
)
from apps.payments.payment_service import (
    handle_payment_success,
    handle_payment_failed,
    _verify_amount_and_currency,
)
from apps.payments.refund_service import apply_refund, create_refund
from apps.payments.webhooks.cashfree_webhook import (
    cashfree_webhook,
    process_cashfree_webhook_payload,
)
from apps.payments.providers.base import CheckoutOrderResult, RefundResult, StatusResult, VerificationResult, WebhookResult
from core.exceptions import ValidationError


def _make_order(**overrides):
    defaults = {
        "status": OrderStatus.PLACED,
        "payment_status": PaymentStatus.PENDING,
        "payment_method": PaymentMethod.CASHFREE,
        "shipping_address": {"line1": "Test"},
        "billing_address": {"line1": "Test"},
        "subtotal": Decimal("1000.00"),
        "grand_total": Decimal("1000.00"),
        "currency": "INR",
    }
    defaults.update(overrides)
    return Order.objects.create(**defaults)


def _make_txn(order, **overrides):
    defaults = {
        "order": order,
        "provider": "cashfree",
        "provider_ref": str(order.id),
        "status": TransactionStatus.PENDING,
        "total_amount": order.grand_total,
        "refunded_amount": Decimal("0.00"),
        "amount": order.grand_total,
        "currency": order.currency,
        "raw_response": {},
    }
    defaults.update(overrides)
    return PaymentTransaction.objects.create(**defaults)


# ─────────────────────────────────────────────────────────────
#  1. Amount & Currency Validation
# ─────────────────────────────────────────────────────────────

class AmountCurrencyValidationTests(TestCase):
    def setUp(self):
        self.order = _make_order()
        self.txn = _make_txn(self.order)

    def test_valid_payment_marks_order_paid(self):
        """Happy path: correct amount → SUCCESS → order marked paid."""
        result = handle_payment_success(
            payment_data={
                "order_id": str(self.order.id),
                "cf_payment_id": "cf-pay-1",
                "payment_status": "SUCCESS",
                "payment_amount": "1000.00",
                "payment_currency": "INR",
            },
            provider_name="cashfree",
        )
        self.assertIsNotNone(result)
        self.txn.refresh_from_db()
        self.assertEqual(self.txn.status, TransactionStatus.SUCCESS)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, PaymentStatus.PAID)

    def test_amount_mismatch_blocks_success(self):
        """Provider pays ₹500 for a ₹1000 order → stays PENDING, order not paid."""
        result = handle_payment_success(
            payment_data={
                "order_id": str(self.order.id),
                "cf_payment_id": "cf-pay-2",
                "payment_status": "SUCCESS",
                "payment_amount": "500.00",
                "payment_currency": "INR",
            },
            provider_name="cashfree",
        )
        self.assertIsNotNone(result)
        self.txn.refresh_from_db()
        # Transaction should NOT be marked as SUCCESS
        self.assertEqual(self.txn.status, TransactionStatus.PENDING)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, PaymentStatus.PENDING)

    def test_currency_mismatch_blocks_success(self):
        """Provider sends USD for an INR order → blocked."""
        result = handle_payment_success(
            payment_data={
                "order_id": str(self.order.id),
                "cf_payment_id": "cf-pay-3",
                "payment_status": "SUCCESS",
                "payment_amount": "1000.00",
                "payment_currency": "USD",
            },
            provider_name="cashfree",
        )
        self.assertIsNotNone(result)
        self.txn.refresh_from_db()
        self.assertEqual(self.txn.status, TransactionStatus.PENDING)

    def test_missing_amount_allows_through(self):
        """If provider doesn't report amount, we allow through (can't verify)."""
        result = handle_payment_success(
            payment_data={
                "order_id": str(self.order.id),
                "cf_payment_id": "cf-pay-4",
                "payment_status": "SUCCESS",
                # No payment_amount field
            },
            provider_name="cashfree",
        )
        self.assertIsNotNone(result)
        self.txn.refresh_from_db()
        self.assertEqual(self.txn.status, TransactionStatus.SUCCESS)

    def test_verify_amount_and_currency_helper(self):
        """Direct unit test of the verification helper."""
        # Match
        ok, reason = _verify_amount_and_currency(
            txn=self.txn,
            payment_data={"payment_amount": "1000.00", "payment_currency": "INR"},
        )
        self.assertTrue(ok)
        self.assertEqual(reason, "")

        # Amount mismatch
        ok, reason = _verify_amount_and_currency(
            txn=self.txn,
            payment_data={"payment_amount": "1.00", "payment_currency": "INR"},
        )
        self.assertFalse(ok)
        self.assertIn("Amount mismatch", reason)

        # Currency mismatch
        ok, reason = _verify_amount_and_currency(
            txn=self.txn,
            payment_data={"payment_amount": "1000.00", "payment_currency": "EUR"},
        )
        self.assertFalse(ok)
        self.assertIn("Currency mismatch", reason)


# ─────────────────────────────────────────────────────────────
#  2. Payment State Machine Guards
# ─────────────────────────────────────────────────────────────

class PaymentStateMachineTests(TestCase):
    def setUp(self):
        self.order = _make_order()

    def test_success_to_failed_transition_blocked(self):
        """SUCCESS txn can't regress to FAILED."""
        txn = _make_txn(self.order, status=TransactionStatus.SUCCESS)
        result = handle_payment_failed(
            payment_data={"order_id": str(self.order.id)},
            provider_name="cashfree",
        )
        txn.refresh_from_db()
        # Should still be SUCCESS — the FAILED transition was blocked
        self.assertEqual(txn.status, TransactionStatus.SUCCESS)

    def test_refunded_to_success_transition_blocked(self):
        """REFUNDED txn can't go back to SUCCESS."""
        txn = _make_txn(self.order, status=TransactionStatus.REFUNDED)
        result = handle_payment_success(
            payment_data={
                "order_id": str(self.order.id),
                "payment_amount": "1000.00",
                "payment_currency": "INR",
            },
            provider_name="cashfree",
        )
        txn.refresh_from_db()
        self.assertEqual(txn.status, TransactionStatus.REFUNDED)

    def test_partially_refunded_to_success_blocked(self):
        """PARTIALLY_REFUNDED txn can't go back to SUCCESS."""
        txn = _make_txn(self.order, status=TransactionStatus.PARTIALLY_REFUNDED)
        result = handle_payment_success(
            payment_data={
                "order_id": str(self.order.id),
                "payment_amount": "1000.00",
            },
            provider_name="cashfree",
        )
        txn.refresh_from_db()
        self.assertEqual(txn.status, TransactionStatus.PARTIALLY_REFUNDED)

    def test_pending_to_success_allowed(self):
        """Pending → SUCCESS is normal flow."""
        txn = _make_txn(self.order)
        handle_payment_success(
            payment_data={
                "order_id": str(self.order.id),
                "payment_amount": "1000.00",
                "payment_currency": "INR",
            },
            provider_name="cashfree",
        )
        txn.refresh_from_db()
        self.assertEqual(txn.status, TransactionStatus.SUCCESS)

    def test_pending_to_failed_allowed(self):
        """Pending → FAILED is normal flow."""
        txn = _make_txn(self.order)
        handle_payment_failed(
            payment_data={"order_id": str(self.order.id)},
            provider_name="cashfree",
        )
        txn.refresh_from_db()
        self.assertEqual(txn.status, TransactionStatus.FAILED)

    def test_failed_to_success_allowed_delayed_webhook(self):
        """FAILED → SUCCESS is allowed (delayed webhook arriving after retry)."""
        txn = _make_txn(self.order, status=TransactionStatus.FAILED)
        handle_payment_success(
            payment_data={
                "order_id": str(self.order.id),
                "payment_amount": "1000.00",
                "payment_currency": "INR",
            },
            provider_name="cashfree",
        )
        txn.refresh_from_db()
        self.assertEqual(txn.status, TransactionStatus.SUCCESS)

    def test_duplicate_success_is_idempotent(self):
        """SUCCESS → SUCCESS is a safe no-op."""
        txn = _make_txn(self.order, status=TransactionStatus.SUCCESS)
        result = handle_payment_success(
            payment_data={"order_id": str(self.order.id)},
            provider_name="cashfree",
        )
        txn.refresh_from_db()
        self.assertEqual(txn.status, TransactionStatus.SUCCESS)


# ─────────────────────────────────────────────────────────────
#  3. Webhook Idempotency & Signature
# ─────────────────────────────────────────────────────────────

@override_settings(CASHFREE_SECRET_KEY="test-secret")
class WebhookIdempotencyTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.order = _make_order()
        self.txn = _make_txn(self.order)

    def _signature(self, payload: bytes) -> str:
        return hmac.new(b"test-secret", payload, hashlib.sha256).hexdigest()

    def test_duplicate_webhook_is_idempotent(self):
        """Same event_id sent twice → second call is a no-op."""
        payload = {
            "event_id": "evt-idem-test-1",
            "data": {
                "payment": {
                    "order_id": str(self.order.id),
                    "cf_payment_id": str(self.txn.provider_ref),
                    "payment_status": "SUCCESS",
                    "payment_amount": 1000.00,
                    "payment_currency": "INR",
                },
                "order": {
                    "order_id": str(self.order.id),
                },
            },
        }
        payload_bytes = json.dumps(payload).encode("utf-8")
        first = process_cashfree_webhook_payload(payload=payload, payload_bytes=payload_bytes)
        second = process_cashfree_webhook_payload(payload=payload, payload_bytes=payload_bytes)

        self.assertFalse(first["duplicate"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(WebhookEvent.objects.filter(event_id="evt-idem-test-1").count(), 1)

    def test_invalid_signature_rejected(self):
        """Bad HMAC → 403."""
        payload = b'{"data":{"payment":{"payment_status":"SUCCESS"}}}'
        request = self.factory.post(
            "/api/v1/payments/webhook/cashfree/",
            data=payload,
            content_type="application/json",
            HTTP_X_WEBHOOK_SIGNATURE="bad-signature",
        )
        response = cashfree_webhook(request)
        self.assertEqual(response.status_code, 403)

    def test_missing_signature_rejected(self):
        """No signature header → 403."""
        payload = b'{"data":{"payment":{"payment_status":"SUCCESS"}}}'
        request = self.factory.post(
            "/api/v1/payments/webhook/cashfree/",
            data=payload,
            content_type="application/json",
            # No signature header
        )
        response = cashfree_webhook(request)
        self.assertEqual(response.status_code, 403)


# ─────────────────────────────────────────────────────────────
#  4. Payment Retry Flow
# ─────────────────────────────────────────────────────────────

class PaymentRetryTests(TestCase):
    def setUp(self):
        self.order = _make_order()
        self.txn = _make_txn(
            self.order,
            status=TransactionStatus.FAILED,
            retry_count=0,
            max_retries=3,
        )

    @patch("apps.payments.services.registry")
    def test_retry_creates_new_transaction(self, mock_registry):
        """Retry on FAILED → new PENDING txn created."""
        from apps.payments.services import retry_payment
        from apps.payments.providers.base import PaymentResult

        mock_provider = MagicMock()
        mock_provider.supported_currencies = ["INR"]
        mock_provider.initiate.return_value = PaymentResult(
            success=True,
            provider_ref="new-cf-order",
            payment_url="https://pay.example.com/session",
            raw_response={"order_id": "new-cf-order"},
        )
        mock_registry.get.return_value = mock_provider

        new_txn = retry_payment(transaction=self.txn, return_url="https://return.example.com")

        self.assertNotEqual(new_txn.id, self.txn.id)
        self.assertEqual(new_txn.status, TransactionStatus.PENDING)
        self.assertEqual(new_txn.order_id, self.order.id)

        self.txn.refresh_from_db()
        self.assertEqual(self.txn.retry_count, 1)
        self.assertEqual(self.txn.status, TransactionStatus.RETRY)

    def test_retry_blocked_at_limit(self):
        """Retry limit reached → ValidationError."""
        from apps.payments.services import retry_payment

        self.txn.retry_count = 3
        self.txn.save(update_fields=["retry_count"])

        with self.assertRaises(ValidationError):
            retry_payment(transaction=self.txn)


class RazorpayCheckoutFlowTests(TestCase):
    def setUp(self):
        self.order = _make_order(payment_method=PaymentMethod.RAZORPAY)

    @patch("apps.payments.services.registry")
    def test_create_checkout_order_creates_created_transaction(self, mock_registry):
        from apps.payments.services import create_checkout_order

        mock_provider = MagicMock()
        mock_provider.supported_currencies = ["INR"]
        mock_provider.create_checkout_order.return_value = CheckoutOrderResult(
            success=True,
            provider_ref="order_test_123",
            amount=Decimal("1000.00"),
            currency="INR",
            key_id="rzp_test_key",
            raw_response={"id": "order_test_123", "key_id": "rzp_test_key"},
        )
        mock_registry.get.return_value = mock_provider

        txn = create_checkout_order(
            order=self.order,
            provider_name="razorpay",
            amount=Decimal("1000.00"),
            currency="INR",
        )

        self.assertEqual(txn.status, TransactionStatus.CREATED)
        self.assertEqual(txn.provider_ref, "order_test_123")
        self.assertEqual(txn.razorpay_order_id, "order_test_123")

    @patch("apps.payments.services.registry")
    def test_verify_checkout_payment_marks_success_and_stores_ids(self, mock_registry):
        from apps.payments.services import verify_checkout_payment

        txn = _make_txn(
            self.order,
            provider="razorpay",
            provider_ref="order_test_123",
            razorpay_order_id="order_test_123",
            status=TransactionStatus.CREATED,
        )

        mock_provider = MagicMock()
        mock_provider.verify_payment_signature.return_value = VerificationResult(
            success=True,
            provider_ref="pay_test_123",
            order_ref="order_test_123",
            raw_response={},
        )
        mock_registry.get.return_value = mock_provider

        verified_txn = verify_checkout_payment(
            provider_name="razorpay",
            razorpay_order_id="order_test_123",
            razorpay_payment_id="pay_test_123",
            razorpay_signature="sig_test_123",
        )

        self.assertEqual(verified_txn.status, TransactionStatus.SUCCESS)
        self.assertEqual(verified_txn.provider_ref, "pay_test_123")
        self.assertEqual(verified_txn.razorpay_order_id, "order_test_123")
        self.assertEqual(verified_txn.razorpay_payment_id, "pay_test_123")
        self.assertEqual(verified_txn.razorpay_signature, "sig_test_123")

    @patch("apps.payments.services.registry")
    def test_razorpay_webhook_updates_checkout_identifiers(self, mock_registry):
        from apps.payments.services import handle_webhook

        txn = _make_txn(
            self.order,
            provider="razorpay",
            provider_ref="order_test_123",
            razorpay_order_id="order_test_123",
            status=TransactionStatus.CREATED,
        )
        mock_provider = MagicMock()
        mock_provider.verify_webhook.return_value = WebhookResult(
            verified=True,
            provider_ref="pay_test_123",
            order_ref=str(self.order.id),
            status="success",
            amount=Decimal("1000.00"),
            currency="INR",
            raw_data={"_provider_order_id": "order_test_123"},
        )
        mock_registry.get.return_value = mock_provider

        log = handle_webhook(
            provider_name="razorpay",
            payload=b'{"event":"payment.captured"}',
            headers={"x-razorpay-signature": "test"},
        )

        txn.refresh_from_db()
        self.assertTrue(log.is_processed)
        self.assertEqual(txn.status, TransactionStatus.SUCCESS)
        self.assertEqual(txn.provider_ref, "pay_test_123")
        self.assertEqual(txn.razorpay_order_id, "order_test_123")
        self.assertEqual(txn.razorpay_payment_id, "pay_test_123")


# ─────────────────────────────────────────────────────────────
#  5. Refund Safety
# ─────────────────────────────────────────────────────────────

class RefundSafetyTests(TestCase):
    def setUp(self):
        self.order = _make_order(
            payment_status=PaymentStatus.PAID,
        )
        self.txn = _make_txn(
            self.order,
            status=TransactionStatus.SUCCESS,
            total_amount=Decimal("1000.00"),
            refunded_amount=Decimal("0.00"),
        )

    def test_refund_cannot_exceed_payment(self):
        """Refund for more than paid amount → ValidationError."""
        with self.assertRaises(ValidationError):
            create_refund(
                order=self.order,
                payment=self.txn,
                amount=Decimal("1500.00"),
                source=RefundSource.AUTO,
            )

    def test_partial_refund_limits_subsequent_refund(self):
        """After partial refund, second refund can't exceed remaining."""
        apply_refund(
            payment=self.txn,
            refund_amount=Decimal("700.00"),
            refund_id="RFND-PARTIAL-1",
            status=RefundStatus.SUCCESS,
            source=RefundSource.AUTO,
        )

        with self.assertRaises(ValidationError):
            create_refund(
                order=self.order,
                payment=self.txn,
                amount=Decimal("400.00"),
                source=RefundSource.AUTO,
            )

    def test_refund_idempotent_on_duplicate(self):
        """Duplicate refund with same refund_id → no double accounting."""
        apply_refund(
            payment=self.txn,
            refund_amount=Decimal("200.00"),
            refund_id="RFND-DUP-TEST",
            cf_refund_id="CF-DUP-1",
            status=RefundStatus.SUCCESS,
            source=RefundSource.AUTO,
        )
        apply_refund(
            payment=self.txn,
            refund_amount=Decimal("200.00"),
            refund_id="RFND-DUP-TEST",
            cf_refund_id="CF-DUP-1",
            status=RefundStatus.SUCCESS,
            source=RefundSource.AUTO,
        )
        self.txn.refresh_from_db()
        self.assertEqual(self.txn.refunded_amount, Decimal("200.00"))
        self.assertEqual(Refund.objects.filter(refund_id="RFND-DUP-TEST").count(), 1)


# ─────────────────────────────────────────────────────────────
#  6. Stock Release on Payment Failure
# ─────────────────────────────────────────────────────────────

class StockReleaseOnFailureTests(TestCase):
    def setUp(self):
        self.order = _make_order()
        self.txn = _make_txn(self.order)

    @patch("apps.inventory.services.release_reservation")
    def test_payment_failed_releases_stock(self, mock_release):
        """Failed payment → release_reservation called."""
        handle_payment_failed(
            payment_data={"order_id": str(self.order.id)},
            provider_name="cashfree",
        )
        self.txn.refresh_from_db()
        self.assertEqual(self.txn.status, TransactionStatus.FAILED)
        mock_release.assert_called_once_with(
            order_id=str(self.order.id),
            notes="Stock released — payment failed.",
        )

    @patch("apps.inventory.services.release_reservation", side_effect=Exception("DB error"))
    def test_stock_release_failure_does_not_crash(self, mock_release):
        """Stock release error is caught — payment failure is still recorded."""
        handle_payment_failed(
            payment_data={"order_id": str(self.order.id)},
            provider_name="cashfree",
        )
        self.txn.refresh_from_db()
        self.assertEqual(self.txn.status, TransactionStatus.FAILED)

    def test_no_stock_release_for_paid_order(self):
        """If order is already paid, don't release stock on a stale failure webhook."""
        self.order.status = OrderStatus.PAID
        self.order.save(update_fields=["status"])
        # Txn already in SUCCESS — state machine should block FAILED
        self.txn.status = TransactionStatus.SUCCESS
        self.txn.save(update_fields=["status"])

        with patch("apps.inventory.services.release_reservation") as mock_release:
            handle_payment_failed(
                payment_data={"order_id": str(self.order.id)},
                provider_name="cashfree",
            )
            mock_release.assert_not_called()


# ─────────────────────────────────────────────────────────────
#  7. Generic Webhook Hardening
# ─────────────────────────────────────────────────────────────

class GenericWebhookHardeningTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_generic_webhook_rejects_cashfree(self):
        """POST to /webhook/cashfree/ generic route → 400."""
        from apps.payments.views import WebhookView

        request = self.factory.post(
            "/api/v1/payments/webhook/cashfree/",
            data=b'{"test": true}',
            content_type="application/json",
        )
        # WebhookView requires no auth
        request.user = MagicMock()
        view = WebhookView.as_view()
        response = view(request, provider="cashfree")
        self.assertEqual(response.status_code, 400)


# ─────────────────────────────────────────────────────────────
#  8. Reconciliation Amount Validation
# ─────────────────────────────────────────────────────────────

class ReconcileAmountValidationTests(TestCase):
    def setUp(self):
        self.order = _make_order()
        self.txn = _make_txn(self.order)

    @patch("apps.payments.services.registry")
    def test_reconcile_with_amount_mismatch_blocks_success(self, mock_registry):
        """Reconcile returns success but amount doesn't match → don't mark paid."""
        from apps.payments.services import reconcile_transaction_status

        mock_provider = MagicMock()
        mock_provider.get_status.return_value = StatusResult(
            success=True,
            provider_ref=str(self.order.id),
            status="success",
            amount=Decimal("500.00"),  # Mismatch: order is 1000
            raw_response={"order_status": "PAID"},
        )
        mock_registry.get.return_value = mock_provider

        result = reconcile_transaction_status(transaction=self.txn)
        self.txn.refresh_from_db()
        # Should NOT be marked SUCCESS due to amount mismatch
        self.assertEqual(self.txn.status, TransactionStatus.PENDING)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, PaymentStatus.PENDING)

    @patch("apps.payments.services.registry")
    def test_reconcile_with_matching_amount_succeeds(self, mock_registry):
        """Reconcile with correct amount → marks paid."""
        from apps.payments.services import reconcile_transaction_status

        mock_provider = MagicMock()
        mock_provider.get_status.return_value = StatusResult(
            success=True,
            provider_ref=str(self.order.id),
            status="success",
            amount=Decimal("1000.00"),
            raw_response={"order_status": "PAID"},
        )
        mock_registry.get.return_value = mock_provider

        result = reconcile_transaction_status(transaction=self.txn)
        self.txn.refresh_from_db()
        self.assertEqual(self.txn.status, TransactionStatus.SUCCESS)

    @patch("apps.payments.services.registry")
    def test_reconcile_state_machine_blocks_refunded_to_success(self, mock_registry):
        """Reconcile can't regress REFUNDED → SUCCESS."""
        from apps.payments.services import reconcile_transaction_status

        self.txn.status = TransactionStatus.REFUNDED
        self.txn.save(update_fields=["status"])

        mock_provider = MagicMock()
        mock_provider.get_status.return_value = StatusResult(
            success=True,
            provider_ref=str(self.order.id),
            status="success",
            amount=Decimal("1000.00"),
            raw_response={},
        )
        mock_registry.get.return_value = mock_provider

        reconcile_transaction_status(transaction=self.txn)
        self.txn.refresh_from_db()
        self.assertEqual(self.txn.status, TransactionStatus.REFUNDED)


class RazorpayStaleCleanupTaskTests(TestCase):
    def setUp(self):
        self.order = _make_order(
            payment_method=PaymentMethod.RAZORPAY,
            payment_status=PaymentStatus.PENDING,
        )
        self.txn = _make_txn(
            self.order,
            provider="razorpay",
            status=TransactionStatus.CREATED,
            provider_ref="order_test_stale_1",
            razorpay_order_id="order_test_stale_1",
        )
        PaymentTransaction.objects.filter(id=self.txn.id).update(
            created_at=timezone.now() - timedelta(minutes=40)
        )

    @override_settings(RAZORPAY_STALE_ORDER_TIMEOUT_MINUTES=20)
    @patch("apps.orders.services.cancel_order")
    @patch("apps.payments.services.reconcile_transaction_status")
    def test_stale_unpaid_razorpay_order_is_cancelled(
        self,
        mock_reconcile,
        mock_cancel_order,
    ):
        from apps.payments.tasks import expire_stale_razorpay_orders_task

        mock_reconcile.side_effect = lambda *, transaction: transaction

        result = expire_stale_razorpay_orders_task()
        self.txn.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(result["cancelled"], 1)
        self.assertEqual(self.txn.status, TransactionStatus.FAILED)
        self.assertEqual(self.order.payment_status, PaymentStatus.FAILED)
        mock_cancel_order.assert_called_once()

    @override_settings(RAZORPAY_STALE_ORDER_TIMEOUT_MINUTES=20)
    @patch("apps.orders.services.cancel_order")
    @patch("apps.payments.services.reconcile_transaction_status")
    def test_stale_previous_attempt_is_skipped_if_newer_attempt_exists(
        self,
        mock_reconcile,
        mock_cancel_order,
    ):
        from apps.payments.tasks import expire_stale_razorpay_orders_task

        _make_txn(
            self.order,
            provider="razorpay",
            status=TransactionStatus.CREATED,
            provider_ref="order_test_newer_1",
            razorpay_order_id="order_test_newer_1",
        )

        result = expire_stale_razorpay_orders_task()
        self.txn.refresh_from_db()

        self.assertEqual(result["cancelled"], 0)
        self.assertEqual(self.txn.status, TransactionStatus.CREATED)
        mock_reconcile.assert_not_called()
        mock_cancel_order.assert_not_called()
