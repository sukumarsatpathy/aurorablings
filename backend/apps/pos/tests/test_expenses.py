"""
Expenses: cash out of the drawer, or UPI, with a bill photo and a remark.

What has to hold:
  * a cash expense lowers the drawer's expected cash by exactly its amount;
  * a UPI expense does not touch the drawer;
  * voiding a cash expense puts it back, once;
  * no approval limit — admins enter these;
  * the shift summary shows them.
"""

from decimal import Decimal
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image
from rest_framework.test import APIClient

from apps.accounts.models import User, UserRole
from apps.pos import expenses, services
from apps.pos.models import CashMovementType, POSExpense, POSTerminal


def bill():
    buf = BytesIO()
    Image.new("RGB", (60, 90), (255, 255, 255)).save(buf, format="JPEG")
    return SimpleUploadedFile("bill.jpg", buf.getvalue(), content_type="image/jpeg")


class ExpenseServiceTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="owner@aurorablings.com", password="x", first_name="O", last_name="W",
            role=UserRole.ADMIN,
        )
        self.terminal = POSTerminal.objects.create(code="SHOP-01", name="Shop")
        self.shift = services.open_shift(
            terminal=self.terminal, staff=self.admin, opening_float=Decimal("2000"),
        )

    def test_cash_expense_comes_out_of_the_drawer(self):
        expense = expenses.record_expense(
            payment_mode="cash", amount="150", remarks="Tea and snacks",
            staff=self.admin, shift=self.shift, bill_image=bill(),
        )
        self.assertEqual(services.expected_cash(self.shift), Decimal("1850.00"))
        self.assertEqual(expense.cash_movement.movement_type, CashMovementType.PAY_OUT)
        self.assertTrue(expense.bill_image.name.endswith(".webp"))

    def test_upi_expense_leaves_the_drawer_alone(self):
        expense = expenses.record_expense(
            payment_mode="upi", amount="800", remarks="Auto to exhibition",
            upi_reference="412345678901", staff=self.admin, shift=self.shift,
        )
        self.assertIsNone(expense.cash_movement)
        self.assertEqual(expense.upi_reference, "412345678901")
        self.assertEqual(services.expected_cash(self.shift), Decimal("2000.00"))

    def test_upi_expense_needs_no_shift(self):
        expense = expenses.record_expense(
            payment_mode="upi", amount="5000", remarks="Stall rent", staff=self.admin,
        )
        self.assertIsNone(expense.shift_id)

    def test_cash_expense_without_an_open_shift_is_refused(self):
        with self.assertRaises(expenses.ExpenseError):
            expenses.record_expense(payment_mode="cash", amount="10", remarks="x", staff=self.admin)

    def test_a_remark_is_required(self):
        with self.assertRaises(expenses.ExpenseError):
            expenses.record_expense(
                payment_mode="upi", amount="10", remarks="  ", staff=self.admin,
            )

    def test_there_is_no_approval_limit(self):
        expense = expenses.record_expense(
            payment_mode="cash", amount="1999", remarks="Packing boxes",
            staff=self.admin, shift=self.shift,
        )
        self.assertEqual(expense.amount, Decimal("1999.00"))

    def test_voiding_a_cash_expense_restores_the_drawer_once(self):
        expense = expenses.record_expense(
            payment_mode="cash", amount="300", remarks="Wrong entry",
            staff=self.admin, shift=self.shift,
        )
        expenses.void_expense(expense=expense, staff=self.admin, reason="typed twice")
        self.assertEqual(services.expected_cash(self.shift), Decimal("2000.00"))
        with self.assertRaises(expenses.ExpenseError):
            expenses.void_expense(expense=expense, staff=self.admin, reason="again")
        self.assertEqual(services.expected_cash(self.shift), Decimal("2000.00"))

    def test_a_cash_expense_on_a_closed_shift_cannot_be_voided(self):
        expense = expenses.record_expense(
            payment_mode="cash", amount="100", remarks="Tea", staff=self.admin, shift=self.shift,
        )
        services.close_shift(shift=self.shift, staff=self.admin, counted_cash=Decimal("1900"))
        with self.assertRaises(expenses.ExpenseError):
            expenses.void_expense(expense=expense, staff=self.admin, reason="late")

    def test_close_balances_with_a_cash_expense(self):
        expenses.record_expense(
            payment_mode="cash", amount="250", remarks="Helper wages",
            staff=self.admin, shift=self.shift,
        )
        closed = services.close_shift(shift=self.shift, staff=self.admin, counted_cash=Decimal("1750"))
        self.assertEqual(closed.variance, Decimal("0.00"))

    def test_shift_summary_lists_expenses(self):
        expenses.record_expense(payment_mode="cash", amount="100", remarks="Tea",
                                staff=self.admin, shift=self.shift)
        expenses.record_expense(payment_mode="upi", amount="400", remarks="Auto",
                                staff=self.admin, shift=self.shift)
        voided = expenses.record_expense(payment_mode="upi", amount="999", remarks="Oops",
                                         staff=self.admin, shift=self.shift)
        expenses.void_expense(expense=voided, staff=self.admin, reason="wrong")

        summary = services.shift_summary(self.shift)["expenses"]
        self.assertEqual(summary["cash"], "100.00")
        self.assertEqual(summary["upi"], "400.00")
        self.assertEqual(summary["total"], "500.00")
        self.assertEqual(len(summary["items"]), 3)


class ExpenseApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="owner@aurorablings.com", password="x", first_name="O", last_name="W",
            role=UserRole.ADMIN,
        )
        self.customer = User.objects.create_user(
            email="c@example.com", password="x", first_name="C", last_name="C",
        )
        self.terminal = POSTerminal.objects.create(code="SHOP-01", name="Shop")
        self.shift = services.open_shift(
            terminal=self.terminal, staff=self.admin, opening_float=Decimal("500"),
        )
        self.client = APIClient()

    def test_record_list_and_void(self):
        self.client.force_authenticate(self.admin)
        res = self.client.post("/api/v1/pos/expenses/", {
            "payment_mode": "cash", "amount": "120", "remarks": "Tea",
            "shift": str(self.shift.id), "bill_image": bill(),
        }, format="multipart")
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(res.data["expected_cash_now"], "380.00")
        self.assertTrue(res.data["bill_image"])

        listing = self.client.get("/api/v1/pos/expenses/", {"shift": str(self.shift.id)}).data
        self.assertEqual(listing["totals"]["cash"], "120.00")
        self.assertEqual(len(listing["results"]), 1)

        voided = self.client.post(
            f"/api/v1/pos/expenses/{res.data['id']}/void/", {"reason": "duplicate"}, format="json",
        )
        self.assertEqual(voided.status_code, 200, voided.content)
        self.assertEqual(voided.data["expected_cash_now"], "500.00")
        self.assertTrue(POSExpense.objects.get().is_voided)

    def test_customers_cannot_record_expenses(self):
        self.client.force_authenticate(self.customer)
        res = self.client.post("/api/v1/pos/expenses/", {
            "payment_mode": "upi", "amount": "1", "remarks": "x",
        })
        self.assertEqual(res.status_code, 403)
