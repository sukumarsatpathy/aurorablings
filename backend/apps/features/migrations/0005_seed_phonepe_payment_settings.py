import json

from django.db import migrations


def seed_phonepe_settings(apps, schema_editor):
    AppSetting = apps.get_model("features", "AppSetting")

    rows = [
        {
            "key": "payment.phonepe",
            "value": json.dumps(
                {
                    "enabled": False,
                    "environment": "sandbox",
                    "merchant_id": "",
                    "salt_key": "",
                    "salt_index": "1",
                    "webhook_secret": "",
                }
            ),
            "value_type": "json",
            "category": "payment",
            "label": "PhonePe",
            "description": "PhonePe gateway configuration.",
            "is_public": False,
            "is_editable": True,
        },
        {
            "key": "payment.phonepe.schema",
            "value": json.dumps(
                {
                    "title": "PhonePe",
                    "description": "Configure PhonePe payments",
                    "fields": {
                        "enabled": {"type": "toggle", "label": "Enabled", "default": False},
                        "environment": {
                            "type": "select",
                            "label": "Environment",
                            "required": True,
                            "options": [
                                {"label": "Sandbox", "value": "sandbox"},
                                {"label": "Production", "value": "production"},
                            ],
                            "default": "sandbox",
                        },
                        "merchant_id": {"type": "text", "label": "Merchant ID", "required": True},
                        "salt_key": {"type": "password", "label": "Salt Key", "required": True},
                        "salt_index": {"type": "text", "label": "Salt Index", "required": True, "default": "1"},
                        "webhook_secret": {"type": "password", "label": "Webhook Secret", "required": False},
                    },
                }
            ),
            "value_type": "json",
            "category": "payment",
            "label": "PhonePe Schema",
            "description": "Schema for payment.phonepe",
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
        ("features", "0004_seed_admin_settings_defaults"),
    ]

    operations = [
        migrations.RunPython(seed_phonepe_settings, noop),
    ]
