from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0017_variant_barcode_label_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="category",
            name="label_paper",
            field=models.CharField(
                choices=[("packed_sticker", "Packed sticker (40 × 15 mm)"), ("tail_tag", "Tail tag (100 × 15 mm)")],
                default="packed_sticker",
                help_text="Barcode label paper used for products in this category.",
                max_length=20,
            ),
        ),
    ]
