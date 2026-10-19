"""
Passwordless checkout: a shopper confirms their email with a 6-digit code
instead of choosing a password.

What matters: a new email gets an account it can only enter by code (no
password), an existing email is never duplicated or altered, inactive/locked
accounts get nothing, and the same send limits and Turnstile check apply as
for normal OTP sign-in.
"""

from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts import services
from apps.accounts.models import EmailOTP, User, UserRole

CHECKOUT_REQUEST_URL = "/api/v1/auth/checkout/otp/request/"
VERIFY_URL = "/api/v1/auth/login/otp/verify/"


def _issue_checkout(email: str) -> str:
    with patch("apps.accounts.tasks.send_login_otp_email.delay") as delay:
        services.request_checkout_otp(email=email)
    assert delay.called, "no email queued"
    return delay.call_args.kwargs["code"]


@override_settings(RATELIMIT_ENABLE=False)
class CheckoutOTPServiceTests(TestCase):

    def setUp(self):
        cache.clear()

    def test_new_email_creates_passwordless_customer_and_sends_code(self):
        code = _issue_checkout(" New.Shopper@Example.com ")

        user = User.objects.get(email="new.shopper@example.com")
        self.assertEqual(user.role, UserRole.CUSTOMER)
        self.assertFalse(user.has_usable_password())
        self.assertFalse(user.is_email_verified)
        self.assertEqual(EmailOTP.objects.filter(user=user).count(), 1)

        result = services.verify_login_otp(email="new.shopper@example.com", code=code)
        self.assertEqual(result["user"], user)
        user.refresh_from_db()
        self.assertTrue(user.is_email_verified)

    def test_existing_email_is_reused_not_duplicated_or_changed(self):
        existing = User.objects.create_user(
            email="riya@example.com", password="Secret123", first_name="Riya",
        )
        code = _issue_checkout("riya@example.com")

        self.assertEqual(User.objects.filter(email="riya@example.com").count(), 1)
        existing.refresh_from_db()
        self.assertTrue(existing.check_password("Secret123"))
        self.assertEqual(existing.first_name, "Riya")
        self.assertEqual(services.verify_login_otp(email="riya@example.com", code=code)["user"], existing)

    def test_inactive_account_gets_no_code(self):
        User.objects.create_user(email="gone@example.com", password="Secret123", is_active=False)
        with patch("apps.accounts.tasks.send_login_otp_email.delay") as delay:
            services.request_checkout_otp(email="gone@example.com")
        delay.assert_not_called()

    def test_resend_cooldown_applies(self):
        _issue_checkout("new@example.com")
        with self.assertRaises(services.OTPCooldownError):
            services.request_checkout_otp(email="new@example.com")
        self.assertEqual(User.objects.filter(email="new@example.com").count(), 1)

    def test_login_otp_still_ignores_unknown_emails(self):
        with patch("apps.accounts.tasks.send_login_otp_email.delay") as delay:
            services.request_login_otp(email="stranger@example.com")
        delay.assert_not_called()
        self.assertFalse(User.objects.filter(email="stranger@example.com").exists())


class CheckoutOTPApiTests(TestCase):

    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def test_full_flow_new_shopper_gets_tokens(self):
        with patch("apps.accounts.tasks.send_login_otp_email.delay") as delay:
            response = self.client.post(CHECKOUT_REQUEST_URL, {"email": "asha@example.com"}, format="json")
        self.assertEqual(response.status_code, 200)
        code = delay.call_args.kwargs["code"]

        response = self.client.post(VERIFY_URL, {"email": "asha@example.com", "code": code}, format="json")
        self.assertEqual(response.status_code, 200)
        body = response.json()["data"]
        self.assertTrue(body["access"])
        self.assertEqual(body["user"]["email"], "asha@example.com")

    def test_second_request_within_cooldown_is_429(self):
        with patch("apps.accounts.tasks.send_login_otp_email.delay"):
            self.client.post(CHECKOUT_REQUEST_URL, {"email": "asha@example.com"}, format="json")
            again = self.client.post(CHECKOUT_REQUEST_URL, {"email": "asha@example.com"}, format="json")
        self.assertEqual(again.status_code, 429)
        self.assertIn("Retry-After", again)

    def test_invalid_email_is_rejected_without_creating_anything(self):
        response = self.client.post(CHECKOUT_REQUEST_URL, {"email": "not-an-email"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(User.objects.count(), 0)

    @patch("core.turnstile.feature_services.get_turnstile_config",
           return_value={"enabled": True, "secret_key": "x"})
    def test_turnstile_is_enforced_and_no_account_is_created(self, _cfg):
        response = self.client.post(CHECKOUT_REQUEST_URL, {"email": "asha@example.com"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error_code"], "turnstile_verification_failed")
        self.assertFalse(User.objects.filter(email="asha@example.com").exists())
