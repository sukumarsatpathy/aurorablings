"""
accounts.tasks
~~~~~~~~~~~~~~
Celery async tasks for account-related side effects.
"""
from celery import shared_task
from core.logging import get_logger

logger = get_logger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_password_reset_email(self, *, user_id: str, token: str):
    """
    Send a password-reset email to the user.

    The raw token (NOT the hash) is included in the link.
    The DB only stores the hash — see services._hash_token().

    Compatibility task: now delegated to notifications engine.
    """
    from apps.accounts.selectors import get_user_by_id

    try:
        user = get_user_by_id(user_id)
        if not user:
            logger.warning("send_reset_email_noop", user_id=user_id, reason="user_not_found")
            return

        from apps.notifications.events import NotificationEvent
        from apps.notifications.tasks import trigger_event_task

        reset_link = f"https://aurorablings.com/reset-password?token={token}"
        trigger_event_task.delay(
            event=NotificationEvent.USER_FORGOT_PASSWORD,
            context={
                "user_name": user.get_full_name() or user.email,
                "customer_name": user.get_full_name() or user.email,
                "reset_url": reset_link,
                "token": token,
                "expiry_hours": 2,
            },
            user_id=str(user.id),
            recipient_email=user.email,
        )

    except Exception as exc:
        logger.error("send_reset_email_failed", user_id=user_id, error=str(exc))
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_welcome_email(self, *, user_id: str):
    """Send a welcome email after successful registration."""
    from apps.accounts.selectors import get_user_by_id

    try:
        user = get_user_by_id(user_id)
        if not user:
            return

        from apps.notifications.email_service import send_welcome_email as send_welcome_email_notification
        send_welcome_email_notification(user)
        logger.info("send_welcome_email_sent", user_id=user_id, email=user.email)
    except Exception as exc:
        logger.error("send_welcome_email_failed", user_id=user_id, error=str(exc))
        raise self.retry(exc=exc)
