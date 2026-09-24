"""
Passwordless sign-in with an emailed one-time code.

What matters: the code only works once, only for a short time, only for the
right person, can't be guessed by brute force, and the endpoint never tells a
stranger whether an email is registered.
"""

from datetime import timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts import services
from apps.accounts.models import EmailOTP, User, UserRole
from core.exceptions import PermissionDeniedError, ValidationError

REQUEST_URL = "/api/v1/auth/login/otp/request/"
VERIFY_URL = "/api/v1/auth/login/otp/verify/"


def _issue(email: str) -> str:
    """Request a code and return the raw digits the email task would have received."""
    with patch("apps.accounts.tasks.send_login_otp_email.delay") as delay:
        services.request_login_otp(email=email)
    assert delay.called, "no email queued"
    return delay.call_args.kwargs["code"]


@override_settings(RATELIMIT_ENABLE=False)
class LoginOTPServiceTests(TestCase):

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            email="riya@example.com", password="Secret123", first_name="Riya",
            role=UserRole.CUSTOMER,
        )

    def test_correct_code_signs_in_and_marks_email_verified(self):
        code = _issue("Riya@Example.com ")
        result = services.verify_login_otp(email="riya@example.com", code=code)

        self.assertEqual(result["user"], self.user)
        self.assertTrue(result["access"])
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_email_verified)

    def test_code_is_stored_hashed_not_raw(self):
        code = _issue("riya@example.com")
        otp = EmailOTP.objects.get(user=self.user)
        self.assertNotIn(code, otp.code_hash)
        self.assertEqual(len(otp.code_hash), 64)

    def test_code_cannot_be_replayed(self):
        code = _issue("riya@example.com")
        services.verify_login_otp(email="riya@example.com", code=code)
        with self.assertRaises(ValidationError):
            services.verify_login_otp(email="riya@example.com", code=code)

    def test_expired_code_is_rejected(self):
        code = _issue("riya@example.com")
        EmailOTP.objects.filter(user=self.user).update(expires_at=timezone.now() - timedelta(seconds=1))
        with self.assertRaises(ValidationError):
            services.verify_login_otp(email="riya@example.com", code=code)

    def test_new_request_invalidates_previous_code(self):
        first = _issue("riya@example.com")
        cache.clear()  # skip the resend cooldown
        second = _issue("riya@example.com")
        if first != second:
            with self.assertRaises(ValidationError):
                services.verify_login_otp(email="riya@example.com", code=first)
        services.verify_login_otp(email="riya@example.com", code=second)

    def test_wrong_guesses_are_counted_and_burn_the_code(self):
        code = _issue("riya@example.com")
        wrong = "000000" if code != "000000" else "111111"
        for _ in range(services.OTP_MAX_VERIFY_ATTEMPTS):
            with self.assertRaises(ValidationError):
                services.verify_login_otp(email="riya@example.com", code=wrong)

        # Counter survived the raised errors (i.e. was not rolled back) ...
        otp = EmailOTP.objects.get(user=self.user)
        self.assertEqual(otp.attempts, services.OTP_MAX_VERIFY_ATTEMPTS)
        self.assertIsNotNone(otp.consumed_at)
        # ... and even the right code is now useless.
        with self.assertRaises(ValidationError):
            services.verify_login_otp(email="riya@example.com", code=code)

    def test_code_for_one_user_does_not_work_for_another(self):
        User.objects.create_user(email="other@example.com", password="Secret123")
        code = _issue("riya@example.com")
        with self.assertRaises(ValidationError):
            services.verify_login_otp(email="other@example.com", code=code)

    def test_unknown_email_sends_nothing(self):
        with patch("apps.accounts.tasks.send_login_otp_email.delay") as delay:
            services.request_login_otp(email="nobody@example.com")
        delay.assert_not_called()
        self.assertFalse(EmailOTP.objects.exists())

    def test_inactive_account_gets_no_code(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        with patch("apps.accounts.tasks.send_login_otp_email.delay") as delay:
            services.request_login_otp(email="riya@example.com")
        delay.assert_not_called()

    def test_locked_account_cannot_sign_in(self):
        code = _issue("riya@example.com")
        self.user.locked_until = timezone.now() + timedelta(minutes=30)
        self.user.save(update_fields=["locked_until"])
        with self.assertRaises(PermissionDeniedError):
            services.verify_login_otp(email="riya@example.com", code=code)

    def test_resend_cooldown_applies_to_unknown_emails_too(self):
        # Otherwise a 429 on the second request would reveal the account exists.
        services.request_login_otp(email="nobody@example.com")
        with self.assertRaises(services.OTPCooldownError):
            services.request_login_otp(email="nobody@example.com")

    def test_staff_can_use_otp(self):
        staff = User.objects.create_user(email="staff@example.com", password="Secret123", role=UserRole.STAFF)
        code = _issue("staff@example.com")
        result = services.verify_login_otp(email="staff@example.com", code=code)
        self.assertEqual(result["user"], staff)


@override_settings(RATELIMIT_ENABLE=False)
class LoginOTPApiTests(TestCase):

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        User.objects.create_user(email="riya@example.com", password="Secret123", first_name="Riya")

    def test_same_response_for_known_and_unknown_email(self):
        with patch("apps.accounts.tasks.send_login_otp_email.delay"):
            known = self.client.post(REQUEST_URL, {"email": "riya@example.com"}, format="json")
            unknown = self.client.post(REQUEST_URL, {"email": "ghost@example.com"}, format="json")
        self.assertEqual(known.status_code, 200)
        self.assertEqual(unknown.status_code, 200)
        self.assertEqual(known.json()["message"], unknown.json()["message"])

    def test_second_request_within_cooldown_is_429(self):
        with patch("apps.accounts.tasks.send_login_otp_email.delay"):
            self.client.post(REQUEST_URL, {"email": "riya@example.com"}, format="json")
            again = self.client.post(REQUEST_URL, {"email": "riya@example.com"}, format="json")
        self.assertEqual(again.status_code, 429)
        self.assertIn("Retry-After", again)

    def test_full_flow_returns_tokens(self):
        with patch("apps.accounts.tasks.send_login_otp_email.delay") as delay:
            self.client.post(REQUEST_URL, {"email": "riya@example.com"}, format="json")
        code = delay.call_args.kwargs["code"]

        response = self.client.post(VERIFY_URL, {"email": "riya@example.com", "code": code}, format="json")
        self.assertEqual(response.status_code, 200)
        body = response.json()["data"]
        self.assertTrue(body["access"])
        self.assertEqual(body["user"]["email"], "riya@example.com")

    def test_malformed_code_is_rejected_before_lookup(self):
        response = self.client.post(VERIFY_URL, {"email": "riya@example.com", "code": "12ab"}, format="json")
        self.assertEqual(response.status_code, 400)

    @patch("core.turnstile.feature_services.get_turnstile_config",
           return_value={"enabled": True, "secret_key": "x"})
    def test_turnstile_is_enforced_when_enabled(self, _cfg):
        response = self.client.post(REQUEST_URL, {"email": "riya@example.com"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error_code"], "turnstile_verification_failed")

        response = self.client.post(VERIFY_URL, {"email": "riya@example.com", "code": "123456"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error_code"], "turnstile_verification_failed")


class LoginOTPEmailTests(TestCase):

    def test_email_renders_code_and_log_does_not_keep_it(self):
        from apps.notifications import email_service
        from apps.notifications.models import NotificationLog

        user = User.objects.create_user(email="riya@example.com", password="Secret123", first_name="Riya")
        captured = {}

        class FakeResult:
            provider = "smtp"
            provider_message_id = ""
            raw_response = {}

        def fake_send(self, *, recipient, subject, html_body, text_body):
            captured["html"] = html_body
            captured["subject"] = subject
            return FakeResult()

        with patch.object(email_service, "_resolve_email_provider", return_value="smtp"), \
             patch.object(email_service, "_load_email_settings",
                          return_value={"enabled": True, "username": "u", "password": "p"}), \
             patch.object(email_service.SMTPSender, "send", fake_send):
            ok = email_service.send_login_otp_email(user, code="499332", expiry_minutes=10)

        self.assertTrue(ok)
        self.assertIn("499332", captured["html"])
        self.assertNotIn("499332", captured["subject"])
        log = NotificationLog.objects.get(template_name="emails/login_otp.html")
        self.assertEqual(log.rendered_context_json.get("otp_code"), "******")
        self.assertNotIn("499332", log.rendered_html_snapshot or "")
        self.assertNotIn("499332", log.plain_text_snapshot or "")
