from unittest import mock

from django.test import TestCase

from apps.accounts.models import User
from apps.features.models import AppSetting
from apps.notifications.events import NotificationEvent
from apps.notifications.models import Notification, NotificationStatus
from apps.notifications.services.email_service import EmailService
from apps.notifications.services.notification_service import NotificationService
from apps.notifications.services.template_service import TemplateService


class NotificationSystemTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="customer@example.com",
            password="pass12345A",
            role="customer",
            first_name="Asha",
            last_name="Sharma",
        )
        self._seed_settings()

    def _seed_settings(self):
        AppSetting.objects.update_or_create(
            key="email.smtp",
            defaults={
                "value_type": "json",
                "category": "notification",
                "value": '{"enabled": true, "host": "smtp.gmail.com", "port": 587, "username": "aurora@example.com", "password": "app-pass", "use_tls": true, "use_ssl": false, "from_email": "Aurora Blings <aurora@example.com>", "reply_to": "connect@aurorablings.com", "timeout": 20}',
            },
        )
        AppSetting.objects.update_or_create(
            key="notifications.settings",
            defaults={
                "value_type": "json",
                "category": "notification",
                "value": '{"email_enabled": true, "queue_enabled": true, "log_failures": true, "max_retries": 3}',
            },
        )
        AppSetting.objects.update_or_create(
            key="notifications.events",
            defaults={
                "value_type": "json",
                "category": "notification",
                "value": '{"order.created": {"enabled": true}, "order.shipped": {"enabled": true}, "order.delivered": {"enabled": true}, "user.forgot_password": {"enabled": true}, "user.blocked": {"enabled": true}, "contact.form.submitted": {"enabled": true}, "product.notify_me": {"enabled": true}}',
            },
        )

    def test_event_toggle_enabled_disabled_behavior(self):
        AppSetting.objects.filter(key="notifications.events").update(
            value='{"order.created": {"enabled": false}}'
        )

        notification = NotificationService.create_notification(
            event_type=NotificationEvent.ORDER_CREATED,
            payload={"order_number": "AB-2026-00001"},
            user=self.user,
            email=self.user.email,
            send_async=False,
        )

        self.assertEqual(notification.status, NotificationStatus.SKIPPED)

    def test_smtp_config_loading_from_appsetting(self):
        config = EmailService.load_smtp_config()
        self.assertTrue(config.enabled)
        self.assertEqual(config.host, "smtp.gmail.com")
        self.assertEqual(config.username, "aurora@example.com")

    def test_notification_record_creation(self):
        notification = NotificationService.create_notification(
            event_type=NotificationEvent.ORDER_CREATED,
            payload={"order_number": "AB-2026-00001"},
            user=self.user,
            email=self.user.email,
            send_async=False,
        )
        self.assertTrue(Notification.objects.filter(id=notification.id).exists())
        self.assertEqual(notification.event_type, NotificationEvent.ORDER_CREATED)

    @mock.patch("apps.notifications.services.email_service.EmailService.send_html_email")
    def test_async_send_success_path(self, mock_send):
        mock_send.return_value = {"provider": "smtp", "status": "sent"}
        notification = NotificationService.create_notification(
            event_type=NotificationEvent.ORDER_CREATED,
            payload={"order_number": "AB-2026-00002", "currency": "INR", "grand_total": "999.00"},
            user=self.user,
            email=self.user.email,
            send_async=False,
        )
        notification.refresh_from_db()
        self.assertEqual(notification.status, NotificationStatus.SENT)
        self.assertEqual(notification.retry_count, 0)

    @mock.patch("apps.notifications.services.email_service.EmailService.send_html_email")
    def test_async_send_failure_path(self, mock_send):
        mock_send.side_effect = Exception("SMTP down")
        notification = NotificationService.create_notification(
            event_type=NotificationEvent.ORDER_CREATED,
            payload={"order_number": "AB-2026-00003"},
            user=self.user,
            email=self.user.email,
            send_async=False,
        )
        notification.refresh_from_db()
        self.assertEqual(notification.status, NotificationStatus.FAILED)
        self.assertGreaterEqual(notification.retry_count, 1)

    @mock.patch("apps.notifications.tasks.send_notification_task.delay")
    def test_retry_action(self, mock_delay):
        notification = Notification.objects.create(
            user=self.user,
            email=self.user.email,
            recipient_email=self.user.email,
            event=NotificationEvent.ORDER_CREATED,
            event_type=NotificationEvent.ORDER_CREATED,
            channel="email",
            status=NotificationStatus.FAILED,
            max_retries=3,
            retry_count=1,
        )
        NotificationService.resend_failed_notification(notification_id=str(notification.id))
        notification.refresh_from_db()
        self.assertEqual(notification.status, NotificationStatus.PENDING)
        mock_delay.assert_called_once()

    def test_forgot_password_email_rendering(self):
        resolved = TemplateService.resolve_template(NotificationEvent.USER_FORGOT_PASSWORD)
        html = TemplateService.render_html(
            template_file=resolved.template_file,
            context={"reset_url": "https://aurora/reset?token=abc", "expiry_hours": 2},
        )
        self.assertIn("Reset Password", html)
        self.assertIn("token=abc", html)

    def test_shipped_email_includes_tracking_and_invoice_url(self):
        resolved = TemplateService.resolve_template(NotificationEvent.ORDER_SHIPPED)
        html = TemplateService.render_html(
            template_file=resolved.template_file,
            context={
                "order_number": "AB-2026-00010",
                "tracking_number": "AWB123",
                "tracking_url": "https://track.example.com/awb",
                "invoice_url": "/api/v1/orders/1/invoice/",
            },
        )
        self.assertIn("AWB123", html)
        self.assertIn("/api/v1/orders/1/invoice/", html)

    def test_blocked_email_includes_duration(self):
        resolved = TemplateService.resolve_template(NotificationEvent.USER_BLOCKED)
        html = TemplateService.render_html(
            template_file=resolved.template_file,
            context={"blocked_hours": 0.5, "reason": "Too many attempts"},
        )
        self.assertIn("0.5", html)
        self.assertIn("Too many attempts", html)
