"""
Occasion dates taken at the counter.

They sit on the order rather than going straight to a customer record because
at the moment staff type them there may not be a customer record yet — it is
created after settlement, by accounts.customer_linking, which is also what
copies these across.

Nullable with no default: most sales will never carry them.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0012_counter_fulfilment_choices"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="contact_date_of_birth",
            field=models.DateField(
                null=True,
                blank=True,
                help_text=(
                    "Optional birthday taken at the counter. Copied to the customer "
                    "record once the sale is linked to one."
                ),
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="contact_anniversary_date",
            field=models.DateField(
                null=True,
                blank=True,
                help_text=(
                    "Optional anniversary taken at the counter. Copied to the "
                    "customer record once the sale is linked to one."
                ),
            ),
        ),
    ]
