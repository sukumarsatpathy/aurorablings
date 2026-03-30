from django.db import migrations


def seed_turnstile_settings(apps, schema_editor):
    AppSetting = apps.get_model("features", "AppSetting")

    rows = [
        {
            "key": "turnstile_enabled",
            "value": "false",
            "value_type": "boolean",
            "category": "advanced",
            "label": "Turnstile Enabled",
            "description": "Enable Cloudflare Turnstile CAPTCHA for public forms and auth endpoints.",
            "is_public": False,
            "is_editable": True,
        },
        {
            "key": "turnstile_site_key",
            "value": "",
            "value_type": "string",
            "category": "advanced",
            "label": "Turnstile Site Key",
            "description": "Cloudflare Turnstile site key used by the frontend widget.",
            "is_public": False,
            "is_editable": True,
        },
        {
            "key": "turnstile_secret_key",
            "value": "",
            "value_type": "string",
            "category": "advanced",
            "label": "Turnstile Secret Key",
            "description": "Cloudflare Turnstile secret key used for backend verification.",
            "is_public": False,
            "is_editable": True,
        },
    ]

    for row in rows:
        AppSetting.objects.get_or_create(key=row["key"], defaults=row)


def noop_reverse(apps, schema_editor):
    # Keep settings rows to avoid accidental production config loss.
    return


class Migration(migrations.Migration):
    dependencies = [
        ("features", "0002_seed_site_urls"),
    ]

    operations = [
        migrations.RunPython(seed_turnstile_settings, noop_reverse),
    ]
