# Generated manually
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("orders", "0003_alter_order_payment_method"),
    ]

    operations = [
        migrations.CreateModel(
            name="Invoice",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("invoice_number", models.CharField(db_index=True, max_length=40, unique=True)),
                ("file", models.FileField(blank=True, upload_to="invoices/%Y/%m/")),
                ("file_size", models.PositiveIntegerField(default=0)),
                ("generated_at", models.DateTimeField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("order", models.OneToOneField(on_delete=models.deletion.CASCADE, related_name="invoice", to="orders.order")),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
