"""Canonical event and channel definitions for notifications."""


class NotificationEvent:
    ORDER_CREATED = "order.created"
    ORDER_SHIPPED = "order.shipped"
    ORDER_DELIVERED = "order.delivered"
    USER_FORGOT_PASSWORD = "user.forgot_password"
    USER_BLOCKED = "user.blocked"
    CONTACT_FORM_SUBMITTED = "contact.form.submitted"
    PRODUCT_NOTIFY_ME = "product.notify_me"
    PRODUCT_RESTOCKED = "product.restocked"

    # Backward-compatible aliases used by existing code paths
    ORDER_PLACED = ORDER_CREATED
    PASSWORD_RESET = USER_FORGOT_PASSWORD
    ORDER_PAID = "order_paid"
    ORDER_PROCESSING = "order_processing"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_COMPLETED = "order_completed"
    PAYMENT_FAILED = "payment_failed"
    PAYMENT_REFUNDED = "payment_refunded"
    RETURN_SUBMITTED = "return_submitted"
    RETURN_APPROVED = "return_approved"
    RETURN_REJECTED = "return_rejected"
    RETURN_REFUND_INITIATED = "return_refund_initiated"
    RETURN_COMPLETED = "return_completed"
    EXCHANGE_SUBMITTED = "exchange_submitted"
    EXCHANGE_APPROVED = "exchange_approved"
    EXCHANGE_SHIPPED = "exchange_shipped"
    EXCHANGE_COMPLETED = "exchange_completed"
    LOW_STOCK_ALERT = "low_stock_alert"
    OUT_OF_STOCK = "out_of_stock"


class NotificationChannel:
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    SMS = "sms"
    PUSH = "push"

    CHOICES = [
        (EMAIL, "Email"),
        (WHATSAPP, "WhatsApp"),
        (SMS, "SMS"),
        (PUSH, "Push"),
    ]


DEFAULT_EVENT_CHANNELS: dict[str, list[str]] = {
    NotificationEvent.ORDER_CREATED: [NotificationChannel.EMAIL],
    NotificationEvent.ORDER_SHIPPED: [NotificationChannel.EMAIL],
    NotificationEvent.ORDER_DELIVERED: [NotificationChannel.EMAIL],
    NotificationEvent.USER_FORGOT_PASSWORD: [NotificationChannel.EMAIL],
    NotificationEvent.USER_BLOCKED: [NotificationChannel.EMAIL],
    NotificationEvent.CONTACT_FORM_SUBMITTED: [NotificationChannel.EMAIL],
    NotificationEvent.PRODUCT_NOTIFY_ME: [NotificationChannel.EMAIL],
    NotificationEvent.PRODUCT_RESTOCKED: [NotificationChannel.EMAIL],
}

EVENT_CHOICES = [
    (NotificationEvent.ORDER_CREATED, NotificationEvent.ORDER_CREATED),
    (NotificationEvent.ORDER_SHIPPED, NotificationEvent.ORDER_SHIPPED),
    (NotificationEvent.ORDER_DELIVERED, NotificationEvent.ORDER_DELIVERED),
    (NotificationEvent.USER_FORGOT_PASSWORD, NotificationEvent.USER_FORGOT_PASSWORD),
    (NotificationEvent.USER_BLOCKED, NotificationEvent.USER_BLOCKED),
    (NotificationEvent.CONTACT_FORM_SUBMITTED, NotificationEvent.CONTACT_FORM_SUBMITTED),
    (NotificationEvent.PRODUCT_NOTIFY_ME, NotificationEvent.PRODUCT_NOTIFY_ME),
    (NotificationEvent.PRODUCT_RESTOCKED, NotificationEvent.PRODUCT_RESTOCKED),
    (NotificationEvent.ORDER_PAID, NotificationEvent.ORDER_PAID),
    (NotificationEvent.ORDER_PROCESSING, NotificationEvent.ORDER_PROCESSING),
    (NotificationEvent.ORDER_CANCELLED, NotificationEvent.ORDER_CANCELLED),
    (NotificationEvent.ORDER_COMPLETED, NotificationEvent.ORDER_COMPLETED),
    (NotificationEvent.PAYMENT_FAILED, NotificationEvent.PAYMENT_FAILED),
    (NotificationEvent.PAYMENT_REFUNDED, NotificationEvent.PAYMENT_REFUNDED),
    (NotificationEvent.RETURN_SUBMITTED, NotificationEvent.RETURN_SUBMITTED),
    (NotificationEvent.RETURN_APPROVED, NotificationEvent.RETURN_APPROVED),
    (NotificationEvent.RETURN_REJECTED, NotificationEvent.RETURN_REJECTED),
    (NotificationEvent.RETURN_REFUND_INITIATED, NotificationEvent.RETURN_REFUND_INITIATED),
    (NotificationEvent.RETURN_COMPLETED, NotificationEvent.RETURN_COMPLETED),
    (NotificationEvent.EXCHANGE_SUBMITTED, NotificationEvent.EXCHANGE_SUBMITTED),
    (NotificationEvent.EXCHANGE_APPROVED, NotificationEvent.EXCHANGE_APPROVED),
    (NotificationEvent.EXCHANGE_SHIPPED, NotificationEvent.EXCHANGE_SHIPPED),
    (NotificationEvent.EXCHANGE_COMPLETED, NotificationEvent.EXCHANGE_COMPLETED),
    (NotificationEvent.LOW_STOCK_ALERT, NotificationEvent.LOW_STOCK_ALERT),
    (NotificationEvent.OUT_OF_STOCK, NotificationEvent.OUT_OF_STOCK),
]
