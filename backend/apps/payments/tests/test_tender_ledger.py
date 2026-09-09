"""
The money path.

These are the assertions manual testing structurally cannot make: a webhook
delivered twice, an over-tender, cash arithmetic that silently inflates revenue.
Each one guards a bug whose cost is discovered at a stall, weeks later, against a
ledger nobody can reconstruct.

If one of these fails, the test is right and the code is wrong.
"""

from decimal import Decimal

from django.test import TestCase

from apps.orders.models import Order, OrderStatus, PaymentStatus
from apps.payments.models import OrderTender, TenderMethod, TenderStatus
from apps.payments import tender_service as ledger


def make_order(total="4798.00", status=OrderStatus.PLACED, payment_status=PaymentStatus.PENDING):
    return Order.objects.create(
        guest_email="walkin@example.com",
        status=status,
        payment_status=payment_status,
        subtotal=Decimal(total),
        grand_total=Decimal(total),
        currency="INR",
    )


class TenderLedgerTests(TestCase):

    # ── 1. Over-tender ───────────────────────────────────────
    def test_tender_cannot_exceed_outstanding_balance(self):
        """A customer who pays by UPI and then also hands over cash must not be
        able to leave more money in the system than the order is worth."""
        order = make_order("1000.00")
        ledger.record_tender(order=order, method=TenderMethod.UPI, amount_applied=Decimal("1000.00"))

        with self.assertRaises(ledger.TenderError):
            ledger.record_tender(
                order=order, method=TenderMethod.CASH, amount_applied=Decimal("500.00"),
            )

        self.assertEqual(order.tenders.count(), 1)
        self.assertEqual(ledger.amount_paid(order), Decimal("1000.00"))

    # ── 2. Webhook idempotency ───────────────────────────────
    def test_duplicate_provider_ref_creates_one_tender(self):
        """Razorpay retries webhooks. The same payment id delivered five times is
        one tender, not five, and not an error."""
        order = make_order("2500.00")

        for _ in range(5):
            ledger.record_tender(
                order=order,
                method=TenderMethod.UPI,
                amount_applied=Decimal("2500.00"),
                provider="razorpay",
                provider_ref="pay_TESTDUPLICATE01",
            )

        self.assertEqual(order.tenders.count(), 1)
        self.assertEqual(ledger.amount_paid(order), Decimal("2500.00"))

    # ── 3. Split arithmetic ──────────────────────────────────
    def test_split_cash_then_upi_settles_exactly(self):
        """Rs 2,000 cash against Rs 4,798 leaves exactly Rs 2,798 for the QR, and
        the second leg closes the order."""
        order = make_order("4798.00")

        ledger.record_tender(
            order=order, method=TenderMethod.CASH,
            amount_applied=Decimal("2000.00"),
            cash_received=Decimal("2000.00"), change_given=Decimal("0.00"),
        )
        order.refresh_from_db()

        self.assertEqual(ledger.balance_due(order), Decimal("2798.00"))
        self.assertEqual(order.payment_status, PaymentStatus.PARTIALLY_PAID)

        ledger.record_tender(
            order=order, method=TenderMethod.UPI,
            amount_applied=Decimal("2798.00"),
            provider="razorpay", provider_ref="pay_TESTSPLITLEG2",
        )
        order.refresh_from_db()

        self.assertEqual(ledger.balance_due(order), Decimal("0.00"))
        self.assertEqual(order.payment_status, PaymentStatus.PAID)
        self.assertEqual(order.status, OrderStatus.PAID)
        self.assertEqual(order.tenders.count(), 2)

    def test_split_handles_odd_paise_on_the_second_leg(self):
        """The UPI leg takes the remainder including odd paise — never a rounded
        figure, or the order can never reach zero."""
        order = make_order("1999.99")
        ledger.record_tender(
            order=order, method=TenderMethod.CASH, amount_applied=Decimal("1000.00"),
        )
        order.refresh_from_db()
        self.assertEqual(ledger.balance_due(order), Decimal("999.99"))

        ledger.record_tender(
            order=order, method=TenderMethod.UPI, amount_applied=Decimal("999.99"),
        )
        order.refresh_from_db()
        self.assertEqual(order.payment_status, PaymentStatus.PAID)

    # ── 4. Cash received vs applied ──────────────────────────
    def test_change_is_a_drawer_movement_not_revenue(self):
        """Rs 2,000 handed over on a Rs 1,850 sale is Rs 1,850 of revenue and
        Rs 150 of change. Conflating them inflates the day's takings."""
        order = make_order("1850.00")

        tender = ledger.record_tender(
            order=order, method=TenderMethod.CASH,
            amount_applied=Decimal("1850.00"),
            cash_received=Decimal("2000.00"),
        )
        order.refresh_from_db()

        self.assertEqual(tender.amount_applied, Decimal("1850.00"))
        self.assertEqual(tender.cash_received, Decimal("2000.00"))
        self.assertEqual(tender.change_given, Decimal("150.00"))
        self.assertEqual(ledger.amount_paid(order), Decimal("1850.00"))
        self.assertEqual(order.payment_status, PaymentStatus.PAID)

    def test_cash_short_is_rejected(self):
        order = make_order("1850.00")
        with self.assertRaises(ledger.TenderError):
            ledger.record_tender(
                order=order, method=TenderMethod.CASH,
                amount_applied=Decimal("1850.00"),
                cash_received=Decimal("1000.00"),
            )
        self.assertEqual(order.tenders.count(), 0)

    # ── 5. Part-paid is a real, recoverable state ────────────
    def test_voiding_the_cash_leg_returns_the_order_to_pending(self):
        """An abandoned split sale: the cash comes back out of the drawer and the
        order stops claiming to hold money."""
        order = make_order("4798.00")
        cash = ledger.record_tender(
            order=order, method=TenderMethod.CASH, amount_applied=Decimal("2000.00"),
        )
        order.refresh_from_db()
        self.assertEqual(order.payment_status, PaymentStatus.PARTIALLY_PAID)

        ledger.void_tender(tender=cash, reason="sale abandoned at counter")
        order.refresh_from_db()

        self.assertEqual(ledger.amount_paid(order), Decimal("0.00"))
        self.assertEqual(order.payment_status, PaymentStatus.PENDING)
        self.assertEqual(order.tenders.filter(status=TenderStatus.VOIDED).count(), 1)

    def test_zero_tender_is_rejected(self):
        order = make_order("500.00")
        with self.assertRaises(ledger.TenderError):
            ledger.record_tender(order=order, method=TenderMethod.CASH, amount_applied=Decimal("0.00"))

    # ── 6. Online orders join the same ledger ────────────────
    def test_online_order_produces_one_tender_so_reporting_is_uniform(self):
        order = make_order("3299.00")
        ledger.record_tender(
            order=order, method=TenderMethod.ONLINE,
            amount_applied=Decimal("3299.00"),
            provider="razorpay", provider_ref="pay_TESTONLINE001",
        )
        order.refresh_from_db()
        self.assertEqual(order.tenders.count(), 1)
        self.assertEqual(order.payment_status, PaymentStatus.PAID)
        self.assertIsNone(order.tenders.first().cash_received)

    def test_refund_states_are_not_overwritten_by_the_ledger(self):
        """The refund flow owns refund statuses; re-deriving from the ledger must
        not walk a refunded order back to 'paid'."""
        order = make_order("1000.00", payment_status=PaymentStatus.PENDING)
        ledger.record_tender(order=order, method=TenderMethod.UPI, amount_applied=Decimal("1000.00"))
        order.refresh_from_db()

        order.payment_status = PaymentStatus.REFUNDED
        order.save(update_fields=["payment_status"])

        self.assertEqual(ledger.derive_payment_status(order), PaymentStatus.REFUNDED)


class GatewaySettlementTests(TestCase):
    """
    The three routes by which a gateway payment can be confirmed — webhook,
    checkout signature verification, and the reconciler — all race each other in
    production. They must converge on one tender.
    """

    def _txn(self, order, amount="2500.00", ref="pay_TESTGATEWAY01"):
        from apps.payments.models import PaymentTransaction, TransactionStatus
        return PaymentTransaction.objects.create(
            order=order,
            provider="razorpay",
            provider_ref=ref,
            razorpay_payment_id=ref,
            status=TransactionStatus.SUCCESS,
            amount=Decimal(amount),
            total_amount=Decimal(amount),
            currency="INR",
        )

    def test_gateway_settlement_creates_one_tender_and_pays_the_order(self):
        order = make_order("2500.00")
        txn = self._txn(order)

        tender = ledger.settle_gateway_payment(payment_transaction=txn)
        order.refresh_from_db()

        self.assertIsNotNone(tender)
        self.assertEqual(order.tenders.count(), 1)
        self.assertEqual(order.payment_status, PaymentStatus.PAID)
        self.assertEqual(order.status, OrderStatus.PAID)
        self.assertEqual(order.payment_method, "razorpay")

    def test_webhook_redelivery_and_reconciler_do_not_double_settle(self):
        """The exact production race: webhook lands, is retried, and the hourly
        reconciler also polls the same payment."""
        order = make_order("2500.00")
        txn = self._txn(order)

        first = ledger.settle_gateway_payment(payment_transaction=txn)
        second = ledger.settle_gateway_payment(payment_transaction=txn)   # retry
        third = ledger.settle_gateway_payment(payment_transaction=txn)    # reconciler
        order.refresh_from_db()

        self.assertIsNotNone(first)
        self.assertIsNone(second, "an already-settled order must be a no-op, not a second tender")
        self.assertIsNone(third)
        self.assertEqual(order.tenders.count(), 1)
        self.assertEqual(ledger.amount_paid(order), Decimal("2500.00"))

    def test_gateway_leg_never_overshoots_a_part_paid_counter_sale(self):
        """A split sale where the QR was raised for the remainder, but the
        transaction row still carries the full order amount."""
        order = make_order("4798.00")
        ledger.record_tender(
            order=order, method=TenderMethod.CASH, amount_applied=Decimal("2000.00"),
        )
        order.refresh_from_db()

        txn = self._txn(order, amount="4798.00", ref="pay_TESTOVERSHOOT")
        ledger.settle_gateway_payment(payment_transaction=txn)
        order.refresh_from_db()

        self.assertEqual(ledger.amount_paid(order), Decimal("4798.00"))
        self.assertEqual(order.tenders.filter(method=TenderMethod.ONLINE).first().amount_applied,
                         Decimal("2798.00"))
        self.assertEqual(order.payment_status, PaymentStatus.PAID)


class RazorpayQrWebhookTests(TestCase):
    """
    A counter QR fires `qr_code.credited`, not `payment.captured`, and puts the
    notes we set at creation on the QR entity rather than the payment. Parse it
    wrong and the customer is paid while the till waits forever.
    """

    def _signed(self, body: dict, secret="whsec_test"):
        import hashlib, hmac, json
        from unittest.mock import patch
        raw = json.dumps(body).encode()
        sig = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        return raw, {"x-razorpay-signature": sig}

    def _provider(self, secret="whsec_test"):
        from apps.payments.providers.razorpay import RazorpayProvider
        provider = RazorpayProvider()
        provider._load_runtime_config = lambda: None
        provider.webhook_secret = secret
        provider.key_id, provider.key_secret = "rzp_test", "secret"
        return provider

    def test_qr_credited_is_a_success_and_finds_the_order(self):
        order_id = "11111111-2222-3333-4444-555555555555"
        body = {
            "event": "qr_code.credited",
            "payload": {
                "qr_code": {"entity": {"id": "qr_ABC", "notes": {"order_id": order_id}}},
                "payment": {"entity": {"id": "pay_XYZ", "amount": 279800, "currency": "INR", "notes": {}}},
            },
        }
        raw, headers = self._signed(body)
        result = self._provider().verify_webhook(payload=raw, headers=headers)

        self.assertTrue(result.verified)
        self.assertEqual(result.status, "success")
        self.assertEqual(result.provider_ref, "pay_XYZ")
        self.assertEqual(result.order_ref, order_id)
        self.assertEqual(result.amount, Decimal("2798.00"))

    def test_a_forged_signature_is_refused(self):
        raw, _ = self._signed({"event": "qr_code.credited", "payload": {}})
        result = self._provider().verify_webhook(
            payload=raw, headers={"x-razorpay-signature": "deadbeef"},
        )
        self.assertFalse(result.verified)
