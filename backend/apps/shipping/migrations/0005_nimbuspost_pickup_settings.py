"""
Add NimbusPost pickup-address fields to the `shipping.nimbuspost` setting.

NimbusPost's create-shipment and serviceability calls need the pickup address
(and its pincode). Existing values are kept; only missing keys are added. The
login password is not stored here — see NIMBUSPOST_EMAIL / NIMBUSPOST_PASSWORD.
"""
import json

from django.db import migrations

NEW_FIELDS = {
    "email": "",
    "pickup_pincode": "",
    "warehouse_name": "",
    "pickup_name": "",
    "pickup_address": "",
    "pickup_address_2": "",
    "pickup_city": "",
    "pickup_state": "",
    "pickup_phone": "",
    "courier_id": "",
}

SCHEMA_FIELDS = {
    "enabled": {"type": "toggle", "label": "Enabled", "default": True},
    "base_url": {"type": "text", "label": "Base URL (blank = https://api.nimbuspost.com/v1)"},
    "email": {"type": "text", "label": "Login email (password goes in the server's NIMBUSPOST_PASSWORD)"},
    "pickup_pincode": {"type": "text", "label": "Pickup pincode"},
    "warehouse_name": {"type": "text", "label": "Warehouse name (as in NimbusPost, max 20 chars)"},
    "pickup_name": {"type": "text", "label": "Pickup contact name"},
    "pickup_address": {"type": "text", "label": "Pickup address line 1"},
    "pickup_address_2": {"type": "text", "label": "Pickup address line 2"},
    "pickup_city": {"type": "text", "label": "Pickup city"},
    "pickup_state": {"type": "text", "label": "Pickup state"},
    "pickup_phone": {"type": "text", "label": "Pickup phone (10 digits)"},
    "courier_id": {"type": "text", "label": "Preferred courier ID (blank = NimbusPost decides)"},
    "webhook_enabled": {"type": "toggle", "label": "Webhook Enabled", "default": True},
    "webhook_secret": {"type": "password", "label": "Webhook Secret"},
    "timeout_seconds": {"type": "text", "label": "Timeout (seconds)", "default": "20"},
}


def forwards(apps, schema_editor):
    AppSetting = apps.get_model("features", "AppSetting")

    row = AppSetting.objects.filter(key="shipping.nimbuspost").first()
    if row:
        try:
            value = json.loads(row.value) if isinstance(row.value, str) else dict(row.value or {})
        except (TypeError, ValueError):
            value = {}
        for key, default in NEW_FIELDS.items():
            value.setdefault(key, default)
        row.value = json.dumps(value)
        row.save(update_fields=["value"])

    schema = AppSetting.objects.filter(key="shipping.nimbuspost.schema").first()
    if schema:
        schema.value = json.dumps({
            "title": "NimbusPost",
            "description": "NimbusPost pickup address and behaviour. Login password is set on the server, not here.",
            "fields": SCHEMA_FIELDS,
        })
        schema.save(update_fields=["value"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("shipping", "0004_seed_multi_provider_settings"),
        ("features", "0001_initial"),
    ]

    operations = [migrations.RunPython(forwards, noop)]
