import json

from django.db import migrations


def forward(apps, schema_editor):
    AppSetting = apps.get_model("features", "AppSetting")

    smtp_value = {
        "enabled": False,
        "host": "smtp.gmail.com",
        "port": 587,
        "username": "",
        "password": "",
        "use_tls": True,
        "use_ssl": False,
        "from_email": "Aurora Blings <no-reply@aurorablings.com>",
        "reply_to": "connect@aurorablings.com",
        "timeout": 20,
    }
    smtp_schema = {
        "title": "SMTP Settings",
        "description": "Configure SMTP for transactional emails.",
        "fields": {
            "enabled": {"type": "toggle", "label": "Enabled", "default": False},
            "host": {"type": "text", "label": "Host", "required": True, "default": "smtp.gmail.com"},
            "port": {"type": "text", "label": "Port", "required": True, "default": "587"},
            "username": {"type": "text", "label": "Username", "required": True},
            "password": {"type": "password", "label": "Password / App Password", "required": True},
            "use_tls": {"type": "toggle", "label": "Use TLS", "default": True},
            "use_ssl": {"type": "toggle", "label": "Use SSL", "default": False},
            "from_email": {"type": "text", "label": "From Email", "required": True},
            "reply_to": {"type": "text", "label": "Reply To"},
            "timeout": {"type": "text", "label": "Timeout (seconds)", "default": "20"},
        },
    }

    bundles = [
        {
            "key": "notification.smtp",
            "value": json.dumps(smtp_value),
            "value_type": "json",
            "category": "notification",
            "label": "SMTP",
            "description": "SMTP credentials used for email notifications.",
            "is_public": False,
            "is_editable": True,
        },
        {
            "key": "notification.smtp.schema",
            "value": json.dumps(smtp_schema),
            "value_type": "json",
            "category": "notification",
            "label": "SMTP Schema",
            "description": "Schema definition for notification.smtp",
            "is_public": False,
            "is_editable": True,
        },
    ]

    for row in bundles:
        AppSetting.objects.update_or_create(key=row["key"], defaults=row)


def backward(apps, schema_editor):
    AppSetting = apps.get_model("features", "AppSetting")
    AppSetting.objects.filter(key__in=["notification.smtp", "notification.smtp.schema"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0009_emailsettings_emaillog"),
        ("features", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
