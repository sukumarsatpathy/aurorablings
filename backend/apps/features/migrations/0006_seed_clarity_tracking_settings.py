from django.db import migrations


def seed_clarity_tracking_settings(apps, schema_editor):
    AppSetting = apps.get_model("features", "AppSetting")

    rows = [
        {
            "key": "CLARITY_TRACKING_ID",
            "value": "",
            "value_type": "string",
            "category": "advanced",
            "label": "Clarity Tracking ID",
            "description": "Microsoft Clarity project tracking ID used for storefront runtime analytics.",
            "is_public": False,
            "is_editable": True,
        },
        {
            "key": "CLARITY_ENABLED",
            "value": "false",
            "value_type": "boolean",
            "category": "advanced",
            "label": "Enable Clarity",
            "description": "Controls whether Microsoft Clarity is injected on storefront pages.",
            "is_public": False,
            "is_editable": True,
        },
    ]

    for row in rows:
        AppSetting.objects.get_or_create(key=row["key"], defaults=row)


def noop(apps, schema_editor):
    return


class Migration(migrations.Migration):
    dependencies = [
        ("features", "0005_seed_phonepe_payment_settings"),
    ]

    operations = [
        migrations.RunPython(seed_clarity_tracking_settings, noop),
    ]
