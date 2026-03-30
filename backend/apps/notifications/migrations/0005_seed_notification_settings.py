import json

from django.db import migrations


DEFAULT_EVENTS = {
    "order.created": {"enabled": True},
    "order.shipped": {"enabled": True},
    "order.delivered": {"enabled": True},
    "user.forgot_password": {"enabled": True},
    "user.blocked": {"enabled": True},
    "contact.form.submitted": {"enabled": True},
    "product.notify_me": {"enabled": True},
}


def forward(apps, schema_editor):
    AppSetting = apps.get_model("features", "AppSetting")
    Notification = apps.get_model("notifications", "Notification")
    NotificationTemplate = apps.get_model("notifications", "NotificationTemplate")

    for row in Notification.objects.all().iterator():
        updated = []
        if not row.event_type:
            row.event_type = row.event or ""
            updated.append("event_type")
        if not row.email:
            row.email = row.recipient_email or ""
            updated.append("email")
        if not row.payload:
            row.payload = row.context_data or {}
            updated.append("payload")
        if not row.error_message:
            row.error_message = row.last_error or ""
            updated.append("error_message")
        if not row.subject_snapshot:
            row.subject_snapshot = row.subject or ""
            updated.append("subject_snapshot")
        if not row.template_key:
            row.template_key = row.event_type or row.event or ""
            updated.append("template_key")
        if updated:
            row.save(update_fields=updated)

    used_keys = set(
        NotificationTemplate.objects.exclude(key__isnull=True).exclude(key__exact="").values_list("key", flat=True)
    )

    for template in NotificationTemplate.objects.all().iterator():
        updated = []
        if not template.key and template.event:
            candidate = template.event
            if candidate in used_keys:
                suffix = (template.channel or "email").lower()
                candidate = f"{candidate}.{suffix}"
            idx = 2
            while candidate in used_keys:
                candidate = f"{template.event}.{idx}"
                idx += 1
            template.key = candidate
            used_keys.add(candidate)
            updated.append("key")
        if not template.template_file:
            mapping = {
                "order.created": "emails/order_confirmation.html",
                "order.shipped": "emails/shipping_confirmation.html",
                "order.delivered": "emails/order_delivered.html",
                "user.forgot_password": "emails/forgot_password.html",
                "user.blocked": "emails/account_blocked.html",
                "contact.form.submitted": "emails/contact_form_notification.html",
                "product.notify_me": "emails/notify_me.html",
            }
            if template.key in mapping:
                template.template_file = mapping[template.key]
                updated.append("template_file")
        if updated:
            template.save(update_fields=updated)

    settings_rows = [
        {
            "key": "email.smtp",
            "value": json.dumps(
                {
                    "enabled": True,
                    "host": "smtp.gmail.com",
                    "port": 587,
                    "username": "",
                    "password": "",
                    "use_tls": True,
                    "use_ssl": False,
                    "from_email": "Aurora Blings <noreply@aurorablings.com>",
                    "reply_to": "connect@aurorablings.com",
                    "timeout": 20,
                }
            ),
            "value_type": "json",
            "category": "notification",
            "label": "SMTP Configuration",
            "description": "SMTP credentials and sender config for email notifications.",
            "is_public": False,
            "is_editable": True,
        },
        {
            "key": "email.smtp.schema",
            "value": json.dumps(
                {
                    "title": "SMTP Settings",
                    "description": "Gmail SMTP configuration",
                    "fields": {
                        "enabled": {"type": "toggle", "label": "Enabled", "default": True},
                        "host": {"type": "text", "label": "Host", "default": "smtp.gmail.com", "required": True},
                        "port": {"type": "text", "label": "Port", "default": "587", "required": True},
                        "username": {"type": "text", "label": "Username", "required": True},
                        "password": {"type": "password", "label": "App Password", "required": True},
                        "use_tls": {"type": "toggle", "label": "Use TLS", "default": True},
                        "use_ssl": {"type": "toggle", "label": "Use SSL", "default": False},
                        "from_email": {"type": "text", "label": "From Email", "required": True},
                        "reply_to": {"type": "text", "label": "Reply To"},
                        "timeout": {"type": "text", "label": "Timeout (seconds)", "default": "20"},
                    },
                }
            ),
            "value_type": "json",
            "category": "notification",
            "label": "SMTP Schema",
            "description": "Schema for email.smtp",
            "is_public": False,
            "is_editable": True,
        },
        {
            "key": "notifications.settings",
            "value": json.dumps(
                {
                    "email_enabled": True,
                    "queue_enabled": True,
                    "log_failures": True,
                    "max_retries": 3,
                }
            ),
            "value_type": "json",
            "category": "notification",
            "label": "Notification Settings",
            "description": "Global notification delivery controls.",
            "is_public": False,
            "is_editable": True,
        },
        {
            "key": "notifications.settings.schema",
            "value": json.dumps(
                {
                    "title": "Notification Settings",
                    "fields": {
                        "email_enabled": {"type": "toggle", "label": "Email Enabled", "default": True},
                        "queue_enabled": {"type": "toggle", "label": "Queue Enabled", "default": True},
                        "log_failures": {"type": "toggle", "label": "Log Failures", "default": True},
                        "max_retries": {"type": "text", "label": "Max Retries", "default": "3"},
                    },
                }
            ),
            "value_type": "json",
            "category": "notification",
            "label": "Notification Settings Schema",
            "description": "Schema for notifications.settings",
            "is_public": False,
            "is_editable": True,
        },
        {
            "key": "notifications.events",
            "value": json.dumps(DEFAULT_EVENTS),
            "value_type": "json",
            "category": "notification",
            "label": "Notification Event Toggles",
            "description": "Per-event notification enablement flags.",
            "is_public": False,
            "is_editable": True,
        },
        {
            "key": "notifications.events.schema",
            "value": json.dumps(
                {
                    "title": "Notification Events",
                    "fields": {
                        "order.created": {"type": "toggle", "label": "Order Created", "default": True},
                        "order.shipped": {"type": "toggle", "label": "Order Shipped", "default": True},
                        "order.delivered": {"type": "toggle", "label": "Order Delivered", "default": True},
                        "user.forgot_password": {"type": "toggle", "label": "Forgot Password", "default": True},
                        "user.blocked": {"type": "toggle", "label": "User Blocked", "default": True},
                        "contact.form.submitted": {"type": "toggle", "label": "Contact Form", "default": True},
                        "product.notify_me": {"type": "toggle", "label": "Back In Stock", "default": True},
                    },
                }
            ),
            "value_type": "json",
            "category": "notification",
            "label": "Notification Events Schema",
            "description": "Schema for notifications.events",
            "is_public": False,
            "is_editable": True,
        },
    ]

    for row in settings_rows:
        AppSetting.objects.update_or_create(key=row["key"], defaults=row)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("features", "0001_initial"),
        ("notifications", "0004_notification_engine_upgrade"),
    ]

    operations = [
        migrations.RunPython(forward, noop),
    ]
