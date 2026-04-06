"""
payments.models
~~~~~~~~~~~~~~~

PaymentTransaction  – one row per payment attempt
WebhookLog          – immutable log of every incoming webhook event
"""

import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _


class TransactionStatus(models.TextChoices):
    CREATED   = "created",   _("Created")
    PENDING   = "pending",   _("Pending")
    SUCCESS   = "success",   _("Success")
    FAILED    = "failed",    _("Failed")
    REFUNDED  = "refunded",  _("Refunded")
    PARTIALLY_REFUNDED = "partially_refunded", _("Partially Refunded")
    CANCELLED = "cancelled", _("Cancelled")
    RETRY     = "retry",     _("Retrying")


class PaymentTransaction(models.Model):
    """
    One row per payment initiation attempt.

    Relationships:
      - One Order can have multiple transactions (retries, re-payments)
      - Only one transaction should ever be in SUCCESS for a given order

    Retry tracking:
      retry_count   – how many times we've retried this transaction
      max_retries   – ceiling (configurable per transaction)
    """

    id             = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order          = models.ForeignKey(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="transactions",
    )
    provider       = models.CharField(max_length=50, db_index=True,
                                      help_text="e.g. 'stripe', 'cashfree'")
    provider_ref   = models.CharField(max_length=255, blank=True, db_index=True,
                                      help_text="Provider's transaction/order ID")
    razorpay_order_id = models.CharField(max_length=255, blank=True, db_index=True)
    razorpay_payment_id = models.CharField(max_length=255, blank=True, db_index=True)
    razorpay_signature = models.TextField(blank=True)
    status         = models.CharField(max_length=25, choices=TransactionStatus.choices,
                                      default=TransactionStatus.PENDING, db_index=True)
    total_amount   = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    refunded_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount         = models.DecimalField(max_digits=12, decimal_places=2)
    currency       = models.CharField(max_length=3, default="INR")

    # Client-side helpers (returned to frontend)
    payment_url    = models.TextField(blank=True, help_text="Redirect URL for hosted pages")
    client_secret  = models.TextField(blank=True, help_text="Stripe client_secret")

    # Retry tracking
    retry_count    = models.PositiveSmallIntegerField(default=0)
    max_retries    = models.PositiveSmallIntegerField(default=3)
    last_error     = models.TextField(blank=True)

    # Raw provider response snapshot
    raw_response   = models.JSONField(default=dict)

    initiated_by   = models.ForeignKey(
        "accounts.User",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="initiated_payments",
    )
    created_at     = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = _("payment transaction")
        verbose_name_plural = _("payment transactions")
        ordering            = ["-created_at"]
        indexes             = [
            models.Index(fields=["order", "status"]),
        ]

    @property
    def can_retry(self) -> bool:
        return (
            self.status in (TransactionStatus.CREATED, TransactionStatus.FAILED, TransactionStatus.RETRY)
            and self.retry_count < self.max_retries
        )

    def __str__(self):
        return f"Txn {self.id} | {self.provider} | {self.status} | {self.amount} {self.currency}"

    @property
    def remaining_refundable_amount(self):
        remaining = self.total_amount - self.refunded_amount
        return remaining if remaining > 0 else 0


class WebhookLog(models.Model):
    """
    Immutable log of every incoming webhook event.

    Rows are NEVER updated or deleted — they are a permanent audit trail.
    The `is_processed` flag is set to True after processing completes.
    `idempotency_key` prevents double-processing of duplicate deliveries.
    """

    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider        = models.CharField(max_length=50, db_index=True)

    # Raw, unmodified request data
    raw_headers     = models.JSONField(default=dict)
    raw_payload     = models.TextField()

    # Parsed fields (filled after successful verification)
    provider_event_id = models.CharField(max_length=255, blank=True, db_index=True)
    provider_ref    = models.CharField(max_length=255, blank=True)
    order_ref       = models.CharField(max_length=255, blank=True)
    event_status    = models.CharField(max_length=30, blank=True)

    # Processing state
    is_verified     = models.BooleanField(default=False)
    is_processed    = models.BooleanField(default=False, db_index=True)
    processing_error = models.TextField(blank=True)
    idempotency_key = models.CharField(max_length=512, blank=True, db_index=True,
                                       help_text="provider + provider_event_id — guard against duplicate delivery")

    # Linked transaction (set after processing)
    transaction     = models.ForeignKey(
        PaymentTransaction,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="webhook_logs",
    )
    created_at      = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name        = _("webhook log")
        verbose_name_plural = _("webhook logs")
        ordering            = ["-created_at"]
        constraints         = [
            models.UniqueConstraint(
                fields=["idempotency_key"],
                condition=models.Q(idempotency_key__gt=""),
                name="unique_webhook_idempotency",
            )
        ]

    def __str__(self):
        return f"Webhook {self.provider} | {self.event_status} | processed={self.is_processed}"


class WebhookEvent(models.Model):
    """
    Idempotency ledger for provider webhook deliveries.

    One row per provider event_id/hash. This is separate from WebhookLog so retries
    can be skipped quickly without parsing/re-applying business logic.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_id = models.CharField(max_length=255, unique=True, db_index=True)
    event_type = models.CharField(max_length=100, blank=True, db_index=True)
    payload = models.JSONField(default=dict)
    processed = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("webhook event")
        verbose_name_plural = _("webhook events")
        ordering = ["-created_at"]

    def __str__(self):
        return f"WebhookEvent {self.event_id} | {self.event_type} | processed={self.processed}"


class RefundStatus(models.TextChoices):
    INITIATED = "initiated", _("Initiated")
    SUCCESS = "success", _("Success")
    FAILED = "failed", _("Failed")
    CANCELLED = "cancelled", _("Cancelled")


class RefundSource(models.TextChoices):
    MANUAL = "manual", _("Manual")
    AUTO = "auto", _("Auto")


class Refund(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="refunds",
    )
    payment = models.ForeignKey(
        PaymentTransaction,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="refunds",
    )
    refund_id = models.CharField(max_length=120, unique=True, db_index=True)
    cf_refund_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=RefundStatus.choices, default=RefundStatus.INITIATED, db_index=True)
    source = models.CharField(max_length=20, choices=RefundSource.choices, default=RefundSource.MANUAL, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("refund")
        verbose_name_plural = _("refunds")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["order", "status"]),
            models.Index(fields=["payment", "status"]),
            models.Index(fields=["source", "created_at"]),
        ]

    def __str__(self):
        return f"Refund {self.refund_id} | {self.status} | {self.amount}"
