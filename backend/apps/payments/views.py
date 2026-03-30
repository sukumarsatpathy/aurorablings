"""
payments.views
~~~~~~~~~~~~~~

Public endpoints:
  GET  /payments/providers/               → list available providers
  POST /payments/initiate/                → start a payment session
  POST /payments/retry/                   → retry a failed transaction
  GET  /payments/status/{txn_id}/         → poll transaction status
  POST /payments/refund/                  → issue a refund  [staff+]

Webhook endpoints (no auth — secured by signature):
  POST /payments/webhook/{provider}/      → receive provider webhook

Admin:
  GET  /payments/admin/transactions/      → all transactions
  GET  /payments/admin/webhooks/          → webhook log
"""
import logging
import json

from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView

from apps.accounts.permissions import IsStaffOrAdmin
from apps.orders.selectors import get_order_by_id
from core.response import success_response, error_response
from core.exceptions import NotFoundError, ValidationError
from core.logging import get_logger

from . import services, selectors
from .providers.registry import registry
from .models import TransactionStatus
from .serializers import (
    PaymentTransactionSerializer,
    InitiatePaymentSerializer,
    RetryPaymentSerializer,
    ReconcilePaymentSerializer,
    RefundSerializer,
    RefundCreateSerializer,
    RefundRecordSerializer,
    WebhookLogSerializer,
    ProviderListSerializer,
)

logger = get_logger(__name__)


def _provider_enabled(provider_name: str) -> bool:
    """
    Resolve whether a payment provider is enabled via AppSetting/ProviderConfig/env.
    """
    name = str(provider_name or "").strip().lower()
    if not name:
        return False

    def _to_bool(value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            v = value.strip().lower()
            if v in {"true", "1", "yes", "on"}:
                return True
            if v in {"false", "0", "no", "off"}:
                return False
        return None

    try:
        from apps.features.models import AppSetting, ProviderConfig

        setting = (
            AppSetting.objects
            .filter(key__in=[
                f"payment.{name}",
                f"payment-{name}",
                f"payment_{name}",
                name,
            ])
            .order_by("-updated_at")
            .first()
        )
        if setting:
            cfg = setting.typed_value
            if isinstance(cfg, str):
                try:
                    parsed = json.loads(cfg)
                    if isinstance(parsed, dict):
                        cfg = parsed
                except Exception:
                    cfg = {}
            if isinstance(cfg, dict):
                enabled = _to_bool(cfg.get("enabled"))
                if enabled is not None:
                    return enabled
                # If config exists but no enabled flag, treat as configured.
                return True

        pc = (
            ProviderConfig.objects
            .filter(provider_key=name, is_active=True, feature__category="payment")
            .order_by("-updated_at")
            .first()
        )
        if pc:
            enabled = _to_bool((pc.config or {}).get("enabled"))
            return True if enabled is None else enabled
    except Exception:
        pass

    # Env fallback for local/dev setups without settings rows.
    if name == "cashfree":
        from django.conf import settings
        return bool(str(getattr(settings, "CASHFREE_APP_ID", "") or "").strip() and str(getattr(settings, "CASHFREE_SECRET_KEY", "") or "").strip())
    if name == "razorpay":
        from django.conf import settings
        return bool(str(getattr(settings, "RAZORPAY_KEY_ID", "") or "").strip() and str(getattr(settings, "RAZORPAY_KEY_SECRET", "") or "").strip())

    return False


def _has_any_payment_toggle(allowed: set[str]) -> bool:
    try:
        from apps.features.models import AppSetting, ProviderConfig

        setting_keys: list[str] = []
        for name in allowed:
            setting_keys.extend([f"payment.{name}", f"payment-{name}", f"payment_{name}", name])
        if AppSetting.objects.filter(key__in=setting_keys).exists():
            return True
        if ProviderConfig.objects.filter(provider_key__in=list(allowed), feature__category="payment").exists():
            return True
    except Exception:
        return False
    return False


# ─────────────────────────────────────────────────────────────
#  Provider Discovery
# ─────────────────────────────────────────────────────────────

class ProviderListView(APIView):
    """GET /payments/providers/ — list all registered providers."""
    permission_classes = [AllowAny]

    def get(self, request):
        allowed = {"cashfree", "razorpay"}
        enforce_enabled = _has_any_payment_toggle(allowed)
        providers = [
            {
                "name":                 p.name,
                "display_name":         p.display_name,
                "supported_currencies": p.supported_currencies,
                "supports_refunds":     p.supports_refunds,
                "supports_webhooks":    p.supports_webhooks,
            }
            for p in registry.all()
            if p.name in allowed and ((not enforce_enabled) or _provider_enabled(p.name))
        ]
        s = ProviderListSerializer(providers, many=True)
        return success_response(data=s.data)


# ─────────────────────────────────────────────────────────────
#  Initiate Payment
# ─────────────────────────────────────────────────────────────

class InitiatePaymentView(APIView):
    """
    POST /payments/initiate/
    Body: { order_id, provider, currency?, return_url? }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        s = InitiatePaymentSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data

        order = get_order_by_id(data["order_id"], user=request.user)
        if not order:
            raise NotFoundError("Order not found.")

        txn = services.initiate_payment(
            order=order,
            provider_name=data["provider"],
            currency=data.get("currency"),
            return_url=data.get("return_url", ""),
            initiated_by=request.user,
        )

        if txn.status == TransactionStatus.FAILED:
            return error_response(
                message=txn.last_error or "Unable to initiate payment session.",
                error_code="payment_initiation_failed",
                status_code=400,
                request_id=getattr(request, "request_id", None),
            )

        return success_response(
            data=PaymentTransactionSerializer(txn).data,
            message="Payment session created.",
            status_code=201,
            request_id=getattr(request, "request_id", None),
        )


# ─────────────────────────────────────────────────────────────
#  Transaction Status (polling)
# ─────────────────────────────────────────────────────────────

class TransactionStatusView(APIView):
    """GET /payments/status/{txn_id}/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, txn_id):
        txn = selectors.get_transaction_by_id(txn_id)
        if not txn:
            raise NotFoundError("Transaction not found.")
        # Scope to owner or staff
        if (
            not request.user.role in ("admin", "staff")
            and txn.order.user != request.user
        ):
            raise NotFoundError("Transaction not found.")
        return success_response(data=PaymentTransactionSerializer(txn).data)


# ─────────────────────────────────────────────────────────────
#  Retry Payment
# ─────────────────────────────────────────────────────────────

class RetryPaymentView(APIView):
    """POST /payments/retry/"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        s = RetryPaymentSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        txn = selectors.get_transaction_by_id(s.validated_data["transaction_id"])
        if not txn:
            raise NotFoundError("Transaction not found.")

        new_txn = services.retry_payment(
            transaction=txn,
            return_url=s.validated_data.get("return_url", ""),
        )
        return success_response(
            data=PaymentTransactionSerializer(new_txn).data,
            message="Payment retry initiated.",
        )


class ReconcilePaymentView(APIView):
    """
    POST /payments/reconcile/
    Body: { order_id }

    Fallback for return-url flow when webhook processing is delayed.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        s = ReconcilePaymentSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        order = get_order_by_id(s.validated_data["order_id"], user=request.user)
        if not order:
            raise NotFoundError("Order not found.")

        txn = services.reconcile_order_payment(order=order)
        return success_response(
            data={
                "order_id": str(order.id),
                "order_status": order.status,
                "payment_status": order.payment_status,
                "transaction": PaymentTransactionSerializer(txn).data if txn else None,
            },
            message="Payment status reconciled.",
        )


# ─────────────────────────────────────────────────────────────
#  Refund
# ─────────────────────────────────────────────────────────────

class RefundView(APIView):
    """POST /payments/refund/  [staff+]"""
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request):
        s = RefundSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        txn = selectors.get_transaction_by_id(s.validated_data["transaction_id"])
        if not txn:
            raise NotFoundError("Transaction not found.")

        result = services.refund_payment(
            transaction=txn,
            amount=s.validated_data.get("amount"),
            reason=s.validated_data.get("reason", ""),
            changed_by=request.user,
        )
        return success_response(data=result, message="Refund processed.")


class RefundCreateView(APIView):
    """
    POST /payments/refunds/ [staff+]
    Body: { order_id, amount, reason? }
    """
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request):
        from .refund_service import create_refund
        from .selectors import get_successful_transaction
        from .models import RefundSource

        s = RefundCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data

        order = get_order_by_id(data["order_id"])
        if not order:
            raise NotFoundError("Order not found.")

        txn = get_successful_transaction(order.id)
        if not txn:
            return error_response(
                message="No successful payment transaction found for this order.",
                error_code="payment_not_found",
                status_code=400,
            )

        refund = create_refund(
            order=order,
            payment=txn,
            amount=data["amount"],
            source=RefundSource.MANUAL,
            reason=data.get("reason", ""),
            metadata={"trigger": "refund_create_api"},
            changed_by=request.user,
        )
        return success_response(
            data=RefundRecordSerializer(refund).data,
            message="Refund request processed.",
            status_code=201,
        )


# ─────────────────────────────────────────────────────────────
#  Webhook  (no auth — signature-verified per provider)
# ─────────────────────────────────────────────────────────────

class WebhookView(APIView):
    """
    POST /payments/webhook/{provider}/

    Security:
      - No session/JWT auth (webhooks are server-to-server)
      - Each provider's verify_webhook() validates the HMAC/signature
      - Raw payload logged BEFORE parsing for non-repudiation
      - Idempotency key prevents double-processing of retried events

    We immediately enqueue to Celery so the view returns 200 fast.
    (Most providers retry on timeout or non-2xx.)
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, provider):
        if not registry.is_registered(provider):
            return error_response(
                message=f"Unknown provider '{provider}'.",
                error_code="unknown_provider",
                status_code=400,
            )

        # Cashfree has a dedicated, hardened endpoint — block generic route
        if provider == "cashfree":
            return error_response(
                message="Use the dedicated Cashfree webhook endpoint.",
                error_code="use_dedicated_endpoint",
                status_code=400,
            )

        # Enqueue async (return 200 immediately to the provider)
        from .tasks import process_webhook_task
        process_webhook_task.delay(
            provider_name=provider,
            payload_str=request.body.decode("utf-8", errors="replace"),
            headers=dict(request.headers),
        )

        logger.info("webhook_enqueued", provider=provider)
        return success_response(data=None, message="Webhook received.")


class CashfreeWebhookView(APIView):
    """
    POST /payments/webhook/cashfree/

    Performs synchronous signature verification + idempotent event processing.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        from .webhooks.cashfree_webhook import cashfree_webhook

        return cashfree_webhook(request)


# ─────────────────────────────────────────────────────────────
#  Admin views
# ─────────────────────────────────────────────────────────────

class AdminTransactionListView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def get(self, request):
        order_id = request.query_params.get("order_id")
        if not order_id:
            return error_response(message="order_id query param required.", status_code=400, error_code="bad_request")
        txns = selectors.get_transactions_for_order(order_id)
        return success_response(data=PaymentTransactionSerializer(txns, many=True).data)


class AdminWebhookLogView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def get(self, request):
        logs = selectors.get_webhook_logs(
            provider=request.query_params.get("provider"),
            is_processed=request.query_params.get("is_processed") == "true" if "is_processed" in request.query_params else None,
            limit=int(request.query_params.get("limit", 50)),
        )
        return success_response(data=WebhookLogSerializer(logs, many=True).data)
