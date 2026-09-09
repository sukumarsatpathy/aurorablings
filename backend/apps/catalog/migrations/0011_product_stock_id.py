from django.db import migrations, models


class Migration(migrations.Migration):
    """
    The counter's stock reference number.

    Nullable and unique: existing products need no backfill, and in Postgres a
    unique index treats every NULL as distinct, so any number of products may
    sit without one.
    """

    dependencies = [
        ("catalog", "0010_productmedia_image_variants"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="stock_id",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Stock reference number used at the counter. Optional, but unique when set.",
                null=True,
                unique=True,
            ),
        ),
    ]
