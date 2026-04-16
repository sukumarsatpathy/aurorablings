from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("banners", "0003_promobanner_editor_style_and_positions"),
    ]

    operations = [
        migrations.AddField(
            model_name="promobanner",
            name="image_large",
            field=models.ImageField(blank=True, null=True, upload_to="promo_banners/"),
        ),
        migrations.AddField(
            model_name="promobanner",
            name="image_medium",
            field=models.ImageField(blank=True, null=True, upload_to="promo_banners/"),
        ),
        migrations.AddField(
            model_name="promobanner",
            name="image_small",
            field=models.ImageField(blank=True, null=True, upload_to="promo_banners/"),
        ),
    ]

