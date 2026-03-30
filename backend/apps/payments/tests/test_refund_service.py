from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from core.exceptions import ValidationError

from apps.orders.models import Order, OrderStatus, PaymentMethod, PaymentStatus
from apps.payments.models import (
    PaymentTransaction,
    Refund,
    RefundSource,
    RefundStatus,
    TransactionStatus,
)
from apps.payments.providers.base import RefundResult
from apps.payments.refund_service import apply_refund, create_refund


class _ProviderStub:
    def __init__(self, result: RefundResult):
        self._result = result

    def refund(self, *, provider_ref: str, amount: Decimal, reason: str = "") -> RefundResult:
        return self._result


class RefundServiceTests(TestCase):
    def setUp(self):
        self.order = Order.objects.create(
            status=OrderStatus.PLACED,
            payment_status=PaymentStatus.PAID,
            payment_method=PaymentMethod.COD,
            shipping_address={"line1": "a"},
            billing_address={"line1": "a"},
            subtotal=Decimal("500.00"),
            shipping_cost=Decimal("0.00"),
            tax_amount=Decimal("0.00"),
            grand_total=Decimal("500.00"),
        )
        self.payment = PaymentTransaction.objects.create(
            order=self.order,
            provider="cashfree",
            provider_ref="cf-order-1",
            status=TransactionStatus.SUCCESS,
            total_amount=Decimal("500.00"),
            refunded_amount=Decimal("0.00"),
            amount=Decimal("500.00"),
            currency="INR",
            raw_response={},
        )

    def test_create_refund_rejects_when_payment_not_refundable(self):
        self.payment.status = TransactionStatus.FAILED
        self.payment.save(update_fields=["status", "updated_at"])
        with self.assertRaises(ValidationError):
            create_refund(
                order=self.order,
                payment=self.payment,
                amount=Decimal("10.00"),
                source=RefundSource.MANUAL,
            )

    def test_create_refund_rejects_over_refund_amount(self):
        with self.assertRaises(ValidationError):
            create_refund(
                order=self.order,
                payment=self.payment,
                amount=Decimal("600.00"),
                source=RefundSource.AUTO,
            )

    def test_manual_partial_refund_updates_payment_and_order_status(self):
        provider = _ProviderStub(
            RefundResult(
                success=True,
                refund_ref="cf-rf-1",
                amount=Decimal("100.00"),
                raw_response={"ok": True},
            )
        )
        with patch("apps.payments.refund_service.registry.get", return_value=provider):
            refund = create_refund(
                order=self.order,
                payment=self.payment,
                amount=Decimal("100.00"),
                source=RefundSource.MANUAL,
            )
        self.payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(refund.status, RefundStatus.SUCCESS)
        self.assertEqual(self.payment.refunded_amount, Decimal("100.00"))
        self.assertEqual(self.payment.status, TransactionStatus.PARTIALLY_REFUNDED)
        self.assertEqual(self.order.payment_status, PaymentStatus.PARTIALLY_REFUNDED)
        self.assertEqual(self.order.status, OrderStatus.PARTIALLY_REFUNDED)

    def test_apply_refund_full_refund_updates_to_refunded(self):
        refund = apply_refund(
            payment=self.payment,
            refund_amount=Decimal("500.00"),
            refund_id="RFND-FULL-1",
            cf_refund_id="CF-REF-1",
            status=RefundStatus.SUCCESS,
            source=RefundSource.AUTO,
        )
        self.payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(refund.status, RefundStatus.SUCCESS)
        self.assertEqual(self.payment.refunded_amount, Decimal("500.00"))
        self.assertEqual(self.payment.status, TransactionStatus.REFUNDED)
        self.assertEqual(self.order.payment_status, PaymentStatus.REFUNDED)
        self.assertEqual(self.order.status, OrderStatus.REFUNDED)

    def test_apply_refund_is_idempotent_for_duplicate_success_webhook(self):
        apply_refund(
            payment=self.payment,
            refund_amount=Decimal("80.00"),
            refund_id="RFND-DUP-1",
            cf_refund_id="CF-RDUP-1",
            status=RefundStatus.SUCCESS,
            source=RefundSource.AUTO,
        )
        apply_refund(
            payment=self.payment,
            refund_amount=Decimal("80.00"),
            refund_id="RFND-DUP-1",
            cf_refund_id="CF-RDUP-1",
            status=RefundStatus.SUCCESS,
            source=RefundSource.AUTO,
        )
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.refunded_amount, Decimal("80.00"))
        self.assertEqual(Refund.objects.filter(refund_id="RFND-DUP-1").count(), 1)

