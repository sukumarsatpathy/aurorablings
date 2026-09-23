"""
The QR endpoint's URL.

`/v1/payment/qr_codes` (singular) is not a Razorpay route. It reaches their
gateway and comes back 404 "no Route matched with those values" — which the
caller cannot tell apart from the QR product being disabled on the account, so
it quietly falls back to a payment link on every sale and the counter never
shows a QR at all. One character, and the whole feature is off.

Pinned here because the failure is silent, plausible-looking, and only visible
against the live API.
"""

from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from apps.payments.providers.razorpay import RazorpayProvider


class _Response:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}
        self.content = b"{}"
        self.text = ""

    def json(self):
        return self._payload


class RazorpayQREndpointTests(TestCase):
    def provider(self):
        provider = RazorpayProvider()
        provider.key_id = "rzp_test_abc123"
        provider.key_secret = "secret"
        return provider

    def test_create_posts_to_the_plural_payments_path(self):
        provider = self.provider()
        payload = {"id": "qr_123", "image_url": "https://rzp.io/i/abc", "close_by": 1}

        with patch.object(provider, "_load_runtime_config"), \
                patch("requests.post", return_value=_Response(200, payload)) as post:
            result = provider.create_qr_code(
                order_id="o1", amount=Decimal("431.55"), currency="INR",
                close_by_minutes=15, metadata={},
            )

        url = post.call_args.args[0] if post.call_args.args else post.call_args.kwargs["url"]
        self.assertEqual(url, "https://api.razorpay.com/v1/payments/qr_codes")
        self.assertTrue(result.success)
        self.assertEqual(result.image_url, "https://rzp.io/i/abc")

    def test_close_posts_to_the_plural_payments_path(self):
        provider = self.provider()

        with patch.object(provider, "_load_runtime_config"), \
                patch("requests.post", return_value=_Response(200)) as post:
            provider.close_qr_code(provider_ref="qr_123")

        url = post.call_args.args[0] if post.call_args.args else post.call_args.kwargs["url"]
        self.assertEqual(url, "https://api.razorpay.com/v1/payments/qr_codes/qr_123/close")

    def test_the_amount_is_sent_in_paise(self):
        """₹431.55 is 43155 paise. A rupee figure here undercharges by 100×."""
        provider = self.provider()

        with patch.object(provider, "_load_runtime_config"), \
                patch("requests.post", return_value=_Response(200, {"id": "qr_1"})) as post:
            provider.create_qr_code(
                order_id="o1", amount=Decimal("431.55"), currency="INR",
                close_by_minutes=15, metadata={},
            )

        self.assertEqual(post.call_args.kwargs["json"]["payment_amount"], 43155)

    def test_the_upi_string_is_kept_so_the_counter_can_draw_the_code(self):
        """
        ``image_content`` is the upi://pay string the QR encodes. Keeping it lets
        the server draw the code inline instead of the tablet downloading
        Razorpay's hosted image after the request — the visible delay at the till.
        """
        provider = self.provider()
        upi = "upi://pay?pa=merchant@icici&am=431.55&cu=INR&tr=qr_9"
        payload = {"id": "qr_9", "image_url": "https://rzp.io/i/x", "image_content": upi}

        with patch.object(provider, "_load_runtime_config"), \
                patch("requests.post", return_value=_Response(200, payload)):
            result = provider.create_qr_code(
                order_id="o1", amount=Decimal("431.55"), currency="INR",
                close_by_minutes=15, metadata={},
            )

        self.assertEqual(result.qr_content, upi)


class CounterQrRenderTests(TestCase):
    def test_a_upi_string_renders_as_an_inline_svg(self):
        from apps.pos.collection_service import qr_data_uri

        uri = qr_data_uri("upi://pay?pa=merchant@icici&am=1.00&cu=INR")
        self.assertTrue(uri.startswith("data:image/svg+xml;base64,"))

    def test_nothing_to_draw_returns_empty_so_the_hosted_image_is_used(self):
        from apps.pos.collection_service import qr_data_uri

        self.assertEqual(qr_data_uri(""), "")
