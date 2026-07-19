from django.db import migrations, models


class Migration(migrations.Migration):
    """AVIF siblings of the WebP derivatives added in 0004.

    Nullable and blank, matching 0004, because AVIF generation is optional:
    PromoBanner.save() skips it when the Pillow build has no AVIF encoder, and
    the storefront <picture> drops the AVIF <source> when these are empty.

    Additive AddFields only — no backfill here. Populating them requires
    re-encoding image data, which does not belong in a migration. Run
    `python manage.py backfill_banner_variants --apply` afterwards.
    """

    dependencies = [
        ("banners", "0004_promobanner_image_variants"),
    ]

    operations = [
        migrations.AddField(
            model_name="promobanner",
            name="image_avif_small",
            field=models.ImageField(blank=True, null=True, upload_to="promo_banners/"),
        ),
        migrations.AddField(
            model_name="promobanner",
            name="image_avif_medium",
            field=models.ImageField(blank=True, null=True, upload_to="promo_banners/"),
        ),
        migrations.AddField(
            model_name="promobanner",
            name="image_avif_large",
            field=models.ImageField(blank=True, null=True, upload_to="promo_banners/"),
        ),
    ]
