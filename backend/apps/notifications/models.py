import uuid
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .events import NotificationChannel, EVENT_CHOICES


class NotificationStatus(models.TextChoices):
    PENDING = "pending", _("Pending")
    SENT = "sent", _("Sent")
    FAILED = "failed", _("Failed")
    SKIPPED = "skipped", _("Skipped")


class NotificationType(models.TextChoices):
    WELCOME = "welcome", _("Welcome")
    ORDER_CONFIRMED = "order_confirmed", _("Order Confirmed")
    RESET_PASSWORD = "reset_password", _("Reset Password")
    SHIPPING_UPDATE = "shipping_update", _("Shipping Update")
    REFUND = "refund", _("Refund")
    CONTACT = "contact", _("Contact")
    PRODUCT_NOTIFY = "product_notify", _("Product Notify")
    CUSTOM = "custom", _("Custom")


class NotificationProvider(models.TextChoices):
    SMTP = "smtp", _("SMTP")
    BREVO = "brevo", _("Brevo")
    TWILIO = "twilio", _("Twilio")
    INTERNAL = "internal", _("Internal")
    OTHER = "other", _("Other")


class NotificationLogStatus(models.TextChoices):
    PENDING = "pending", _("Pending")
    SENT = "sent", _("Sent")
    FAILED = "failed", _("Failed")
    RETRYING = "retrying", _("Retrying")
    CANCELLED = "cancelled", _("Cancelled")


class NotificationTemplate(models.Model):
    """
    Template registry.

    key/code: business event key (e.g. order.created or WELCOME_EMAIL)
    template_file: whitelisted Django template file path.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField(max_length=100, unique=True, null=True, blank=True, db_index=True)
    code = models.CharField(max_length=120, blank=True, db_index=True)
    name = models.CharField(max_length=200)
    subject_template = models.CharField(max_length=500, blank=True)
    template_file = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)

    # Legacy compatibility fields
    event = models.CharField(max_length=100, choices=EVENT_CHOICES, blank=True, db_index=True)
    channel = models.CharField(max_length=20, choices=NotificationChannel.CHOICES, default=NotificationChannel.EMAIL)
    body_template = models.TextField(blank=True)
    html_body_template = models.TextField(blank=True)

    # Dashboard-ready fields
    html_template = models.TextField(blank=True)
    text_template = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["key", "event", "channel"]

    def __str__(self):
        return f"{self.key or self.code or self.event or 'template'} ({self.channel})"


class Notification(models.Model):
    """
    Outbox notification row.

    New fields follow enterprise event schema while legacy fields are retained
    for current serializers/admin compatibility.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="notifications",
    )

    # Required schema fields
    email = models.EmailField(blank=True)
    event_type = models.CharField(max_length=100, db_index=True, blank=True)
    channel = models.CharField(max_length=20, choices=NotificationChannel.CHOICES, default=NotificationChannel.EMAIL)
    status = models.CharField(max_length=15, choices=NotificationStatus.choices, default=NotificationStatus.PENDING, db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    subject_snapshot = models.CharField(max_length=500, blank=True)
    template_key = models.CharField(max_length=100, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Legacy compatibility fields
    event = models.CharField(max_length=100, choices=EVENT_CHOICES, blank=True, db_index=True)
    template = models.ForeignKey(
        NotificationTemplate,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="notifications",
    )
    recipient_email = models.EmailField(blank=True)
    recipient_phone = models.CharField(max_length=20, blank=True)
    subject = models.CharField(max_length=500, blank=True)
    body = models.TextField(blank=True)
    html_body = models.TextField(blank=True)
    context_data = models.JSONField(default=dict, blank=True)
    provider_ref = models.CharField(max_length=255, blank=True)
    retry_count = models.PositiveSmallIntegerField(default=0)
    max_retries = models.PositiveSmallIntegerField(default=3)
    last_error = models.TextField(blank=True)
    send_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["event_type", "status"]),
            models.Index(fields=["channel", "status"]),
            models.Index(fields=["user", "event_type"]),
        ]

    @property
    def recipient(self) -> str:
        return self.email or self.recipient_email

    @property
    def can_retry(self) -> bool:
        return self.status == NotificationStatus.FAILED and self.retry_count < self.max_retries

    def __str__(self):
        return f"{self.event_type or self.event} -> {self.recipient} [{self.status}]"


class NotificationAttempt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE, related_name="attempts")
    attempt_no = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(max_length=15, choices=NotificationStatus.choices)
    error_message = models.TextField(blank=True)
    provider_response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["created_at"]
        unique_together = [("notification", "attempt_no")]

    def __str__(self):
        return f"Attempt {self.attempt_no} / {self.notification_id}"


class NotificationLog(models.Model):
    """Immutable delivery log powering admin notification dashboard."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Modern dashboard fields
    channel = models.CharField(max_length=20, choices=NotificationChannel.CHOICES, default=NotificationChannel.EMAIL, db_index=True)
    notification_type = models.CharField(max_length=40, choices=NotificationType.choices, default=NotificationType.CUSTOM, db_index=True)
    recipient = models.CharField(max_length=255, db_index=True, blank=True)
    subject = models.CharField(max_length=500, blank=True)
    provider = models.CharField(max_length=20, choices=NotificationProvider.choices, default=NotificationProvider.SMTP, db_index=True)
    provider_message_id = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=NotificationLogStatus.choices, default=NotificationLogStatus.PENDING, db_index=True)
    template_name = models.CharField(max_length=255, blank=True, db_index=True)
    rendered_context_json = models.JSONField(default=dict, blank=True)
    rendered_html_snapshot = models.TextField(blank=True)
    plain_text_snapshot = models.TextField(blank=True)
    error_message = models.TextField(blank=True)
    error_code = models.CharField(max_length=120, blank=True)
    attempts_count = models.PositiveSmallIntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    created_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_notification_logs",
    )
    related_object_type = models.CharField(max_length=80, blank=True)
    related_object_id = models.CharField(max_length=80, blank=True)

    # Legacy compatibility fields
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE, related_name="logs", null=True, blank=True)
    attempt_number = models.PositiveSmallIntegerField(default=1)
    success = models.BooleanField(default=False)
    provider_ref = models.CharField(max_length=255, blank=True)
    error = models.TextField(blank=True)
    raw_response = models.JSONField(default=dict, blank=True)
    attempted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-attempted_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["channel", "status"]),
            models.Index(fields=["provider", "status"]),
            models.Index(fields=["notification_type", "created_at"]),
        ]

    def __str__(self):
        return f"{self.notification_type} -> {self.recipient or self.notification_id} [{self.status}]"


class NotificationProviderSettings(models.Model):
    provider_type = models.CharField(max_length=20, choices=NotificationProvider.choices, unique=True)
    config = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=False, db_index=True)
    last_tested_at = models.DateTimeField(null=True, blank=True)
    last_test_status = models.CharField(max_length=20, choices=NotificationLogStatus.choices, blank=True)
    last_test_message = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["provider_type"]

    def __str__(self):
        return f"{self.provider_type} ({'active' if self.is_active else 'inactive'})"


class NotifySubscription(models.Model):
    """
    Back-in-stock subscription tracker.
    One active subscription per (product,user) or (product,email).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE, related_name="notify_subscriptions")
    user = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="notify_subscriptions",
    )
    name = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True, db_index=True)
    phone = models.CharField(max_length=20, blank=True)
    is_notified = models.BooleanField(default=False, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    unsubscribe_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "user"],
                condition=Q(user__isnull=False),
                name="uniq_notify_subscription_product_user",
            ),
            models.UniqueConstraint(
                fields=["product", "email"],
                condition=Q(email__gt=""),
                name="uniq_notify_subscription_product_email",
            ),
        ]
        indexes = [
            models.Index(fields=["product", "is_notified"]),
            models.Index(fields=["created_at", "is_notified"]),
        ]

    def __str__(self):
        identity = self.user.email if self.user_id and self.user else self.email or self.phone or "guest"
        return f"{self.product.name} -> {identity}"


class ContactQueryStatus(models.TextChoices):
    NEW = "new", _("New")
    READ = "read", _("Read")
    RESOLVED = "resolved", _("Resolved")


class ContactQuery(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150)
    email = models.EmailField(db_index=True)
    phone = models.CharField(max_length=20, blank=True)
    subject = models.CharField(max_length=200, blank=True)
    message = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=ContactQueryStatus.choices,
        default=ContactQueryStatus.NEW,
        db_index=True,
    )
    is_read = models.BooleanField(default=False, db_index=True)
    source = models.CharField(max_length=30, blank=True, default="web")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["is_read", "created_at"]),
        ]

    def __str__(self):
        return f"{self.name} <{self.email}> ({self.subject or 'Contact Query'})"


class EmailSettings(models.Model):
    smtp_host = models.CharField(max_length=255, default="smtp.gmail.com")
    smtp_port = models.PositiveIntegerField(default=587)
    smtp_user = models.CharField(max_length=255, blank=True)
    smtp_password = models.CharField(max_length=255, blank=True)
    from_email = models.CharField(max_length=255, default="Aurora Blings <no-reply@aurorablings.com>")
    use_tls = models.BooleanField(default=True)
    enabled = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Email Settings"
        verbose_name_plural = "Email Settings"

    def __str__(self):
        return f"SMTP ({'Enabled' if self.enabled else 'Disabled'})"


class EmailLog(models.Model):
    STATUS_SENT = "sent"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_SENT, "Sent"),
        (STATUS_FAILED, "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="email_logs",
    )
    recipient = models.EmailField(db_index=True)
    email_type = models.CharField(max_length=100, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, db_index=True)
    subject = models.CharField(max_length=255, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.email_type} -> {self.recipient} ({self.status})"

