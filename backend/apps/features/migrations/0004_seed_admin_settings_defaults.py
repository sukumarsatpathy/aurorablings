import json

from django.db import migrations


def seed_admin_settings_defaults(apps, schema_editor):
    AppSetting = apps.get_model("features", "AppSetting")

    rows = [
        {
            "key": "default_currency",
            "value": "INR",
            "value_type": "string",
            "category": "general",
            "label": "Currency",
            "description": "Default storefront currency code/symbol.",
            "is_public": True,
            "is_editable": True,
        },
        {
            "key": "branding_logo_url",
            "value": "",
            "value_type": "string",
            "category": "branding",
            "label": "Brand Logo URL",
            "description": "Public logo URL used in transactional emails and documents.",
            "is_public": False,
            "is_editable": True,
        },
        {
            "key": "branding_favicon_url",
            "value": "",
            "value_type": "string",
            "category": "branding",
            "label": "Site Favicon",
            "description": "Favicon URL/path used by storefront and admin pages.",
            "is_public": True,
            "is_editable": True,
        },
        {
            "key": "branding_site_name",
            "value": "Aurora Blings",
            "value_type": "string",
            "category": "branding",
            "label": "Site Name",
            "description": "Primary brand name for site UI and emails.",
            "is_public": True,
            "is_editable": True,
        },
        {
            "key": "branding_site_title",
            "value": "Aurora Blings",
            "value_type": "string",
            "category": "branding",
            "label": "Site Title",
            "description": "Browser/page title fallback.",
            "is_public": True,
            "is_editable": True,
        },
        {
            "key": "branding_tagline",
            "value": "",
            "value_type": "string",
            "category": "branding",
            "label": "Tagline",
            "description": "Short brand subtitle/tagline.",
            "is_public": True,
            "is_editable": True,
        },
        {
            "key": "branding_footer_text",
            "value": "Aurora Blings. All Rights are reserved.",
            "value_type": "string",
            "category": "branding",
            "label": "Footer Text",
            "description": "Footer line used in storefront and email templates.",
            "is_public": True,
            "is_editable": True,
        },
        {
            "key": "branding.settings",
            "value": json.dumps(
                {
                    "site_name": "Aurora Blings",
                    "tagline": "",
                    "logo_url": "",
                }
            ),
            "value_type": "json",
            "category": "branding",
            "label": "Branding Settings",
            "description": "Structured branding settings used by emails, invoices, and templates.",
            "is_public": False,
            "is_editable": True,
        },
        {
            "key": "payment.cashfree",
            "value": json.dumps(
                {
                    "enabled": False,
                    "environment": "sandbox",
                    "app_id": "",
                    "secret_key": "",
                    "webhook_secret": "",
                }
            ),
            "value_type": "json",
            "category": "payment",
            "label": "Cashfree",
            "description": "Cashfree gateway configuration.",
            "is_public": False,
            "is_editable": True,
        },
        {
            "key": "payment.cashfree.schema",
            "value": json.dumps(
                {
                    "title": "Cashfree",
                    "description": "Configure Cashfree payments",
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
                        "app_id": {"type": "text", "label": "App ID", "required": True, "placeholder": "CF_APP_ID"},
                        "secret_key": {
                            "type": "password",
                            "label": "Secret Key",
                            "required": True,
                            "placeholder": "CF_SECRET_KEY",
                        },
                        "webhook_secret": {
                            "type": "password",
                            "label": "Webhook Secret",
                            "required": False,
                            "placeholder": "Webhook secret",
                        },
                    },
                }
            ),
            "value_type": "json",
            "category": "payment",
            "label": "Cashfree Schema",
            "description": "Schema for payment.cashfree",
            "is_public": False,
            "is_editable": True,
        },
        {
            "key": "payment.razorpay",
            "value": json.dumps(
                {
                    "enabled": False,
                    "key_id": "",
                    "key_secret": "",
                    "webhook_secret": "",
                }
            ),
            "value_type": "json",
            "category": "payment",
            "label": "Razorpay",
            "description": "Razorpay gateway configuration.",
            "is_public": False,
            "is_editable": True,
        },
        {
            "key": "payment.razorpay.schema",
            "value": json.dumps(
                {
                    "title": "Razorpay",
                    "description": "Configure Razorpay payments",
                    "fields": {
                        "enabled": {"type": "toggle", "label": "Enabled", "default": False},
                        "key_id": {"type": "text", "label": "Key ID", "required": True},
                        "key_secret": {"type": "password", "label": "Key Secret", "required": True},
                        "webhook_secret": {"type": "password", "label": "Webhook Secret", "required": False},
                    },
                }
            ),
            "value_type": "json",
            "category": "payment",
            "label": "Razorpay Schema",
            "description": "Schema for payment.razorpay",
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
        ("features", "0003_seed_turnstile_settings"),
    ]

    operations = [
        migrations.RunPython(seed_admin_settings_defaults, noop),
    ]
