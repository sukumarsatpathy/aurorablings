from django.db import migrations
from django.utils import timezone


def set_completed_orders_as_paid(apps, schema_editor):
    Order = apps.get_model("orders", "Order")
    now = timezone.now()

    Order.objects.filter(
        status="completed",
        payment_status="pending",
    ).update(
        payment_status="paid",
        paid_at=now,
        updated_at=now,
    )


def noop_reverse(apps, schema_editor):
    # Intentionally no reverse to avoid downgrading valid paid records.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0004_alter_order_order_number"),
    ]

    operations = [
        migrations.RunPython(set_completed_orders_as_paid, noop_reverse),
    ]

