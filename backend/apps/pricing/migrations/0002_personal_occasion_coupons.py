"""
Personal coupons: a coupon that belongs to one customer.

Needed for the birthday / anniversary gift programme. Without ``assigned_user``
the only way to give one customer a code is to create a public code with
``usage_limit=1``, which means the first person it is forwarded to spends it —
and a gift that a stranger can redeem is not a gift.

The unique constraint is the idempotency key for the daily sweep: one coupon
per customer, per occasion, per calendar year, enforced by the database rather
than by the task remembering what it did.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pricing", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="coupon",
            name="assigned_user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="personal_coupons",
                to=settings.AUTH_USER_MODEL,
                help_text="If set, only this customer may redeem the coupon.",
            ),
        ),
        migrations.AddField(
            model_name="coupon",
            name="occasion",
            field=models.CharField(
                blank=True,
                default="",
                max_length=20,
                choices=[("birthday", "Birthday"), ("anniversary", "Anniversary")],
                help_text="Why this personal coupon was issued. Blank for campaign coupons.",
            ),
        ),
        migrations.AddField(
            model_name="coupon",
            name="occasion_year",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="coupon",
            constraint=models.UniqueConstraint(
                condition=models.Q(("assigned_user__isnull", False)),
                fields=("assigned_user", "occasion", "occasion_year"),
                name="pricing_unique_occasion_coupon_per_user_year",
            ),
        ),
    ]
