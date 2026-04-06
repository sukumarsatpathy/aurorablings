from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0003_webhookevent"),
    ]

    operations = [
        migrations.AddField(
            model_name="paymenttransaction",
            name="razorpay_order_id",
            field=models.CharField(blank=True, db_index=True, max_length=255),
        ),
        migrations.AddField(
            model_name="paymenttransaction",
            name="razorpay_payment_id",
            field=models.CharField(blank=True, db_index=True, max_length=255),
        ),
        migrations.AddField(
            model_name="paymenttransaction",
            name="razorpay_signature",
            field=models.TextField(blank=True),
        ),
    ]
