"""
Barcode and label name on every variant.

Every existing variant gets a barcode here, in the order it was created, so the
counter can start printing labels for stock already on the shelves without
anyone opening each product. New variants get one on first save.

On Postgres the numbers come from a sequence (catalog_variant_barcode_seq),
created here and moved past the last number handed out, so two variants saved
at the same moment cannot collide.
"""

from django.db import migrations, models

SEQUENCE = "catalog_variant_barcode_seq"
FIRST = 10_000_001


def assign_barcodes(apps, schema_editor):
    ProductVariant = apps.get_model("catalog", "ProductVariant")
    postgres = schema_editor.connection.vendor == "postgresql"

    if postgres:
        schema_editor.execute(
            f"CREATE SEQUENCE IF NOT EXISTS {SEQUENCE} START WITH {FIRST} MINVALUE {FIRST} MAXVALUE 99999999"
        )

    number = FIRST
    for variant in ProductVariant.objects.filter(barcode__isnull=True).order_by("created_at", "sku"):
        variant.barcode = str(number)
        variant.save(update_fields=["barcode"])
        number += 1

    if postgres and number > FIRST:
        # The next nextval() returns `number`.
        schema_editor.execute(f"SELECT setval('{SEQUENCE}', %s, false)", [number])


def drop_sequence(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(f"DROP SEQUENCE IF EXISTS {SEQUENCE}")


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0016_fill_swatch_colours"),
    ]

    operations = [
        migrations.AddField(
            model_name="productvariant",
            name="barcode",
            field=models.CharField(
                blank=True, editable=False, max_length=32, null=True, unique=True,
                help_text="Printed on the counter label and scanned at the till. Assigned automatically.",
            ),
        ),
        migrations.AddField(
            model_name="productvariant",
            name="label_name",
            field=models.CharField(
                blank=True, max_length=20,
                help_text="Short name printed on the label. Leave blank to build it from the product and options.",
            ),
        ),
        migrations.RunPython(assign_barcodes, drop_sequence),
    ]
