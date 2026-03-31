from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0005_fix_completed_orders_pending_payment"),
    ]

    operations = [
        migrations.AlterField(
            model_name="order",
            name="payment_method",
            field=models.CharField(
                blank=True,
                choices=[
                    ("cod", "Cash on Delivery"),
                    ("cashfree", "Cashfree"),
                    ("razorpay", "Razorpay"),
                    ("phonepe", "PhonePe"),
                    ("stripe", "Stripe"),
                    ("upi", "UPI"),
                    ("bank_transfer", "Bank Transfer"),
                ],
                max_length=20,
            ),
        ),
    ]
