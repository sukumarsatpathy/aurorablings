"""
Seed the switch for website guest checkout.

On by default (that is the feature being shipped). Turning it off in admin puts
checkout back exactly as it was: email OTP required, no guest prepaid orders.
"""

from django.db import migrations


ROW = {
    "key": "checkout_guest_enabled",
    "value": "true",
    "value_type": "boolean",
    "category": "general",
    "label": "Checkout: allow guest checkout",
    "description": (
        "Lets shoppers pay on the website without confirming an email or creating an "
        "account. Name, phone and delivery address are still required (the courier needs "
        "them); email is optional. Set to false to require the email code again."
    ),
    "is_public": True,
    "is_editable": True,
}


def seed(apps, schema_editor):
    AppSetting = apps.get_model("features", "AppSetting")
    AppSetting.objects.get_or_create(key=ROW["key"], defaults=ROW)


def noop(apps, schema_editor):
    return


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0013_order_contact_occasion_dates"),
        ("features", "0006_seed_clarity_tracking_settings"),
    ]

    operations = [
        migrations.RunPython(seed, noop),
    ]
