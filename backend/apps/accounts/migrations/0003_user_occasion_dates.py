"""
Birthday and anniversary on the customer record.

Both nullable, both optional everywhere. They exist so the daily occasion sweep
(apps/pricing/tasks.py) can find whose gift is due; nothing else reads them.

Indexed on purpose: the sweep filters month/day across every customer row once
a day, and an unindexed DateField makes that a full table scan that gets slower
as the shop grows.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_address_accounts_unique_default_address_per_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="date_of_birth",
            field=models.DateField(
                null=True,
                blank=True,
                db_index=True,
                help_text="Used only to send a birthday gift coupon. Optional.",
                verbose_name="date of birth",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="anniversary_date",
            field=models.DateField(
                null=True,
                blank=True,
                db_index=True,
                help_text="Used only to send an anniversary gift coupon. Optional.",
                verbose_name="anniversary",
            ),
        ),
    ]
