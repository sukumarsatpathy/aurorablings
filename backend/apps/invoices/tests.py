from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.orders.models import Order, OrderItem, OrderStatus, PaymentStatus, PaymentMethod
from apps.invoices.models import Invoice
from apps.invoices.services.invoice_service import InvoiceService


class InvoiceSystemTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.customer = User.objects.create_user(
            email="customer-invoice@example.com",
            password="pass12345A",
            role="customer",
            first_name="Nia",
            last_name="Kapoor",
        )
        self.other_customer = User.objects.create_user(
            email="other-invoice@example.com",
            password="pass12345A",
            role="customer",
            first_name="Ria",
            last_name="Kapoor",
        )
        self.admin = User.objects.create_user(
            email="admin-invoice@example.com",
            password="pass12345A",
            role="admin",
            is_staff=True,
        )
        self.order = self._create_order(self.customer)

    def _create_order(self, user):
        order = Order.objects.create(
            user=user,
            status=OrderStatus.PLACED,
            payment_status=PaymentStatus.PAID,
            payment_method=PaymentMethod.RAZORPAY,
            shipping_address={
                "full_name": "Nia Kapoor",
                "line1": "12 Lake Road",
                "city": "Bengaluru",
                "state": "Karnataka",
                "pincode": "560001",
                "country": "India",
                "phone": "9999999999",
            },
            billing_address={
                "full_name": "Nia Kapoor",
                "line1": "12 Lake Road",
                "city": "Bengaluru",
                "state": "Karnataka",
                "pincode": "560001",
                "country": "India",
                "phone": "9999999999",
            },
            subtotal=Decimal("1000.00"),
            discount_amount=Decimal("50.00"),
            shipping_cost=Decimal("40.00"),
            tax_amount=Decimal("10.00"),
            grand_total=Decimal("1000.00"),
            currency="INR",
        )
        OrderItem.objects.create(
            order=order,
            variant=None,
            sku="SKU-001",
            product_name="Aurora Ring",
            variant_name="Gold",
            product_snapshot={},
            quantity=1,
            unit_price=Decimal("1000.00"),
            line_total=Decimal("1000.00"),
        )
        return order

    def test_invoice_pdf_generation_for_valid_order(self):
        invoice = InvoiceService.get_or_generate_invoice(order=self.order, regenerate=True)
        self.assertTrue(invoice.file.name.endswith(".pdf"))
        self.assertGreater(invoice.file_size, 0)

    def test_customer_can_download_own_invoice(self):
        self.client.force_authenticate(self.customer)
        response = self.client.get(f"/api/v1/orders/{self.order.id}/invoice/")
        self.assertEqual(response.status_code, 200)

    def test_customer_cannot_download_another_user_invoice(self):
        self.client.force_authenticate(self.other_customer)
        response = self.client.get(f"/api/v1/orders/{self.order.id}/invoice/")
        self.assertEqual(response.status_code, 404)

    def test_admin_can_download_any_invoice(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(f"/api/v1/orders/{self.order.id}/invoice/")
        self.assertEqual(response.status_code, 200)

    def test_admin_order_list_invoice_link_visible(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get("/api/v1/orders/admin/")
        self.assertEqual(response.status_code, 200)
        rows = response.data.get("data") or []
        self.assertTrue(rows)
        self.assertIn("invoice_url", rows[0])

    def test_regenerate_invoice_action_works(self):
        self.client.force_authenticate(self.admin)
        first = InvoiceService.get_or_generate_invoice(order=self.order, regenerate=False)
        response = self.client.post(f"/api/v1/orders/admin/{self.order.id}/invoice/regenerate/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Invoice.objects.filter(order=self.order).exists())
        refreshed = Invoice.objects.get(order=self.order)
        self.assertEqual(refreshed.id, first.id)
        self.assertIsNotNone(refreshed.generated_at)
