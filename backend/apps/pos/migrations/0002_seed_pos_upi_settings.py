"""
Seed the settings that decide how the counter takes UPI.

The counter collects UPI on the shop's own Paytm merchant account (Soundbox /
standee), not through Razorpay. Razorpay stays for the website. These rows make
that a setting rather than a code path, so switching back is an admin edit, not
a deploy.

Created with get_or_create: an admin who has already filled these in keeps
their values if the migration ever runs again.
"""

from django.db import migrations


ROWS = [
    {
        "key": "pos_upi_provider",
        "value": "paytm",
        "value_type": "string",
        "category": "general",
        "label": "POS: UPI provider at the counter",
        "description": (
            "'paytm' = customers pay the shop's Paytm merchant UPI (Soundbox announces it) and "
            "staff confirm with the UPI reference. 'razorpay' = the old Razorpay dynamic QR "
            "confirmed by webhook. The website always uses Razorpay regardless of this."
        ),
        "is_public": False,
        "is_editable": True,
    },
    {
        "key": "pos_upi_vpa",
        "value": "",
        "value_type": "string",
        "category": "general",
        "label": "POS: Paytm merchant UPI ID",
        "description": (
            "The merchant UPI ID printed on the Paytm standee (e.g. paytmqr1234abcd@paytm). "
            "When set, the counter shows a QR with the exact amount pre-filled. When empty, "
            "staff ask the customer to scan the Paytm standee and confirm manually."
        ),
        "is_public": False,
        "is_editable": True,
    },
    {
        "key": "pos_upi_payee_name",
        "value": "Aurora Blings",
        "value_type": "string",
        "category": "general",
        "label": "POS: UPI payee name",
        "description": "Name shown in the customer's UPI app when they scan the counter QR.",
        "is_public": False,
        "is_editable": True,
    },
]


def seed(apps, schema_editor):
    AppSetting = apps.get_model("features", "AppSetting")
    for row in ROWS:
        AppSetting.objects.get_or_create(key=row["key"], defaults=row)


def noop(apps, schema_editor):
    return


class Migration(migrations.Migration):
    dependencies = [
        ("pos", "0001_initial"),
        ("features", "0006_seed_clarity_tracking_settings"),
    ]

    operations = [
        migrations.RunPython(seed, noop),
    ]
