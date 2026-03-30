from django.db import migrations


def seed_site_urls(apps, schema_editor):
    AppSetting = apps.get_model("features", "AppSetting")

    defaults = [
        {
            "key": "site.frontend_url",
            "value": "",
            "value_type": "string",
            "category": "general",
            "label": "Site Frontend URL",
            "description": "Public storefront URL used in email links (e.g. https://aurorablings.com).",
            "is_public": False,
            "is_editable": True,
        },
        {
            "key": "site.backend_url",
            "value": "",
            "value_type": "string",
            "category": "general",
            "label": "Site Backend URL",
            "description": "Public API/base URL used for invoice links in emails (e.g. https://api.aurorablings.com).",
            "is_public": False,
            "is_editable": True,
        },
    ]

    for row in defaults:
        AppSetting.objects.update_or_create(
            key=row["key"],
            defaults=row,
        )


def unseed_site_urls(apps, schema_editor):
    AppSetting = apps.get_model("features", "AppSetting")
    AppSetting.objects.filter(key__in=["site.frontend_url", "site.backend_url"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("features", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_site_urls, unseed_site_urls),
    ]

