from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.orders.models import Order, OrderStatus, PaymentMethod, PaymentStatus
from apps.payments.health_service import PaymentHealthService
from apps.payments.models import PaymentTransaction, TransactionStatus


def _make_order(**overrides):
    defaults = {
        "status": OrderStatus.PLACED,
        "payment_status": PaymentStatus.PENDING,
        "payment_method": PaymentMethod.RAZORPAY,
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
        "provider": "razorpay",
        "provider_ref": "order_test_health",
        "status": TransactionStatus.FAILED,
        "total_amount": order.grand_total,
        "refunded_amount": Decimal("0.00"),
        "amount": order.grand_total,
        "currency": order.currency,
        "raw_response": {},
        "last_error": "Auto-cancelled: unpaid Razorpay checkout expired after 20 minutes.",
    }
    defaults.update(overrides)
    return PaymentTransaction.objects.create(**defaults)


class RazorpayStaleHealthMetricTests(TestCase):
    def test_stale_auto_cancel_metric_counts_recent_rows(self):
        service = PaymentHealthService()
        order = _make_order()
        txn = _make_txn(order)
        PaymentTransaction.objects.filter(id=txn.id).update(
            updated_at=timezone.now() - timedelta(hours=1)
        )

        result = service._check_razorpay_stale_auto_cancellations(checked_at=timezone.now())
        self.assertEqual(result["check"], "razorpay_stale_auto_cancellations")
        self.assertEqual(result["status"], "healthy")
        self.assertEqual(result["details"]["auto_cancelled_orders"], 1)

    def test_stale_auto_cancel_metric_warns_when_threshold_crossed(self):
        service = PaymentHealthService()
        for _ in range(service.RAZORPAY_AUTO_CANCEL_WARNING_THRESHOLD + 1):
            _make_txn(_make_order())

        result = service._check_razorpay_stale_auto_cancellations(checked_at=timezone.now())
        self.assertEqual(result["status"], "warning")
