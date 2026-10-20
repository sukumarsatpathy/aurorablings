"""
Post-delivery review requests.

What matters: customers are asked once, a few days after delivery, only about
products they haven't reviewed; guests, recent deliveries and old orders are
left alone; and the email links straight to the open review form.
"""
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import User
from apps.catalog.models import Category, Product, ProductVariant
from apps.orders.models import Order, OrderItem, OrderStatus
from apps.reviews.models import ProductReview, ReviewReminder
from apps.reviews.reminders import send_post_delivery_review_reminders

NOW = timezone.now()


@override_settings(REVIEW_REMINDER_DELAY_DAYS=4, REVIEW_REMINDER_WINDOW_DAYS=30)
class ReviewReminderTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(email="riya@example.com", password="Secret123", first_name="Riya")
        category = Category.objects.create(name="Bangles", slug="bangles")
        self.p1 = self._product("Laal Noor", "laal-noor", category)
        self.p2 = self._product("Rose Meher", "rose-meher", category)
        self.trigger = mock.patch("apps.notifications.services.notification_service.trigger_event")
        self.trigger_event = self.trigger.start()
        self.addCleanup(self.trigger.stop)

    def _product(self, name, slug, category):
        product = Product.objects.create(name=name, slug=slug, category=category, is_active=True)
        ProductVariant.objects.create(
            product=product, sku=slug.upper(), price=Decimal("399.00"), stock_quantity=5, is_active=True, is_default=True,
        )
        return product

    def _order(self, *, user=None, delivered_days_ago=5, status=OrderStatus.DELIVERED, products=None):
        order = Order.objects.create(
            user=user if user is not None else self.customer,
            status=status,
            shipping_address={}, billing_address={},
            subtotal=Decimal("798.00"), grand_total=Decimal("798.00"),
            delivered_at=NOW - timedelta(days=delivered_days_ago),
        )
        for product in products or [self.p1, self.p2]:
            variant = product.variants.first()
            OrderItem.objects.create(
                order=order, variant=variant, sku=variant.sku, product_name=product.name,
                product_snapshot={}, quantity=1, unit_price=Decimal("399.00"), line_total=Decimal("399.00"),
            )
        return order

    def test_asks_about_each_product_with_direct_review_links(self):
        order = self._order()
        result = send_post_delivery_review_reminders(now=NOW)

        self.assertEqual(result["sent"], 1)
        context = self.trigger_event.call_args.kwargs["context"]
        self.assertEqual(context["order_number"], order.order_number)
        self.assertEqual([p["name"] for p in context["products"]], ["Laal Noor", "Rose Meher"])
        self.assertTrue(context["products"][0]["url"].endswith("/product/laal-noor?review=1"))
        self.assertEqual(self.trigger_event.call_args.kwargs["recipient_email"], "riya@example.com")

    def test_each_order_is_asked_only_once(self):
        self._order()
        send_post_delivery_review_reminders(now=NOW)
        second = send_post_delivery_review_reminders(now=NOW + timedelta(days=1))
        self.assertEqual(second["sent"], 0)
        self.assertEqual(self.trigger_event.call_count, 1)

    def test_already_reviewed_products_are_left_out(self):
        self._order()
        ProductReview.objects.create(product=self.p1, user=self.customer, rating=5, title="Love", comment="Lovely")
        send_post_delivery_review_reminders(now=NOW)
        names = [p["name"] for p in self.trigger_event.call_args.kwargs["context"]["products"]]
        self.assertEqual(names, ["Rose Meher"])

    def test_nothing_left_to_review_marks_done_without_email(self):
        order = self._order(products=[self.p1])
        ProductReview.objects.create(product=self.p1, user=self.customer, rating=5, title="Love", comment="Lovely")
        result = send_post_delivery_review_reminders(now=NOW)
        self.assertEqual(result["skipped"], 1)
        self.trigger_event.assert_not_called()
        self.assertTrue(ReviewReminder.objects.filter(order=order).exists())

    def test_timing_window(self):
        self._order(delivered_days_ago=2)    # too soon
        self._order(delivered_days_ago=45)   # before the window
        self._order(status=OrderStatus.SHIPPED, delivered_days_ago=5)
        result = send_post_delivery_review_reminders(now=NOW)
        self.assertEqual(result["sent"], 0)

    def test_completed_orders_count_too(self):
        self._order(status=OrderStatus.COMPLETED)
        self.assertEqual(send_post_delivery_review_reminders(now=NOW)["sent"], 1)

    def test_dry_run_sends_and_records_nothing(self):
        self._order()
        result = send_post_delivery_review_reminders(now=NOW, dry_run=True)
        self.assertEqual(result["sent"], 1)
        self.trigger_event.assert_not_called()
        self.assertFalse(ReviewReminder.objects.exists())


class ReviewRequestEmailTests(TestCase):
    def test_template_renders_products_and_links(self):
        from django.template.loader import render_to_string

        html = render_to_string("emails/review_request.html", {
            # The shared base template expects branding (as TemplateService supplies).
            "branding_logo_url": "https://aurorablings.com/logo.png", "logo_url": "https://aurorablings.com/logo.png",
            "customer_name": "Riya", "order_number": "AB-1001",
            "products": [{"name": "Laal Noor", "url": "https://aurorablings.com/product/laal-noor?review=1", "image": None}],
        })
        self.assertIn("Riya", html)
        self.assertIn("AB-1001", html)
        self.assertIn("https://aurorablings.com/product/laal-noor?review=1", html)
        self.assertEqual(len(mail.outbox), 0)
