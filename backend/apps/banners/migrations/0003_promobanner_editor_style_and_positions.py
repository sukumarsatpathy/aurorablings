from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("banners", "0002_promobanner_shape_color_promobanner_subtitle_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="promobanner",
            name="title",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AddField(
            model_name="promobanner",
            name="badge_bold_x",
            field=models.PositiveSmallIntegerField(default=8),
        ),
        migrations.AddField(
            model_name="promobanner",
            name="badge_bold_y",
            field=models.PositiveSmallIntegerField(default=22),
        ),
        migrations.AddField(
            model_name="promobanner",
            name="badge_color",
            field=models.CharField(default="#1a1a1a", max_length=20),
        ),
        migrations.AddField(
            model_name="promobanner",
            name="badge_text_x",
            field=models.PositiveSmallIntegerField(default=22),
        ),
        migrations.AddField(
            model_name="promobanner",
            name="badge_text_y",
            field=models.PositiveSmallIntegerField(default=22),
        ),
        migrations.AddField(
            model_name="promobanner",
            name="cta_border_color",
            field=models.CharField(default="#1a1a1a", max_length=20),
        ),
        migrations.AddField(
            model_name="promobanner",
            name="cta_text_color",
            field=models.CharField(default="#1a1a1a", max_length=20),
        ),
        migrations.AddField(
            model_name="promobanner",
            name="cta_x",
            field=models.PositiveSmallIntegerField(default=8),
        ),
        migrations.AddField(
            model_name="promobanner",
            name="cta_y",
            field=models.PositiveSmallIntegerField(default=80),
        ),
        migrations.AddField(
            model_name="promobanner",
            name="subtitle_color",
            field=models.CharField(default="#1a1a1a", max_length=20),
        ),
        migrations.AddField(
            model_name="promobanner",
            name="subtitle_x",
            field=models.PositiveSmallIntegerField(default=8),
        ),
        migrations.AddField(
            model_name="promobanner",
            name="subtitle_y",
            field=models.PositiveSmallIntegerField(default=64),
        ),
        migrations.AddField(
            model_name="promobanner",
            name="title_color",
            field=models.CharField(default="#1a1a1a", max_length=20),
        ),
        migrations.AddField(
            model_name="promobanner",
            name="title_x",
            field=models.PositiveSmallIntegerField(default=8),
        ),
        migrations.AddField(
            model_name="promobanner",
            name="title_y",
            field=models.PositiveSmallIntegerField(default=46),
        ),
    ]
