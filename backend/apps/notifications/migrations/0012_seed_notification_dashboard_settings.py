import json

from django.db import migrations


def forward(apps, schema_editor):
    AppSetting = apps.get_model("features", "AppSetting")

    rows = [
        {
            "key": "notification.delivery",
            "value": json.dumps({
                "provider": "smtp",
                "max_retry": 3,
                "timeout": 15,
                "healthcheck_enabled": True,
            }),
            "value_type": "json",
            "category": "notification",
            "label": "Notification Delivery",
            "description": "Core provider selection and retry controls for notifications.",
            "is_public": False,
            "is_editable": True,
        },
        {
            "key": "notification.delivery.schema",
            "value": json.dumps({
                "title": "Notification Delivery",
                "fields": {
                    "provider": {
                        "type": "select",
                        "label": "Default Provider",
                        "default": "smtp",
                        "options": [
                            {"label": "SMTP", "value": "smtp"},
                            {"label": "Brevo", "value": "brevo"},
                        ],
                    },
                    "max_retry": {"type": "text", "label": "Max Retry", "default": "3"},
                    "timeout": {"type": "text", "label": "Provider Timeout (seconds)", "default": "15"},
                    "healthcheck_enabled": {"type": "toggle", "label": "Healthcheck Enabled", "default": True},
                },
            }),
            "value_type": "json",
            "category": "notification",
            "label": "Notification Delivery Schema",
            "description": "Schema definition for notification.delivery",
            "is_public": False,
            "is_editable": True,
        },
        {
            "key": "notification.brevo",
            "value": json.dumps({
                "enabled": False,
                "api_key": "",
                "from_email": "",
                "from_name": "Aurora Blings",
                "timeout": 15,
            }),
            "value_type": "json",
            "category": "notification",
            "label": "Brevo",
            "description": "Brevo provider settings for notification delivery.",
            "is_public": False,
            "is_editable": True,
        },
        {
            "key": "notification.brevo.schema",
            "value": json.dumps({
                "title": "Brevo Settings",
                "fields": {
                    "enabled": {"type": "toggle", "label": "Enabled", "default": False},
                    "api_key": {"type": "password", "label": "API Key", "required": True},
                    "from_email": {"type": "text", "label": "From Email", "required": True},
                    "from_name": {"type": "text", "label": "From Name", "default": "Aurora Blings"},
                    "timeout": {"type": "text", "label": "Timeout (seconds)", "default": "15"},
                },
            }),
            "value_type": "json",
            "category": "notification",
            "label": "Brevo Schema",
            "description": "Schema definition for notification.brevo",
            "is_public": False,
            "is_editable": True,
        },
    ]

    for row in rows:
        AppSetting.objects.update_or_create(key=row["key"], defaults=row)


def backward(apps, schema_editor):
    AppSetting = apps.get_model("features", "AppSetting")
    AppSetting.objects.filter(
        key__in=[
            "notification.delivery",
            "notification.delivery.schema",
            "notification.brevo",
            "notification.brevo.schema",
        ]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0011_notificationprovidersettings_and_more"),
        ("features", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
