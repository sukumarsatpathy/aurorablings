"""
Product photos can show a combination of options (e.g. Violet + 2-6), not just
one. The single `attribute_value` tag becomes the `attribute_values` set;
existing tags are copied over, and copied back (first one) on rollback.
The old column is dropped in 0020, in its own transaction.
"""

from django.db import migrations, models


def copy_tag_to_set(apps, schema_editor):
    ProductMedia = apps.get_model("catalog", "ProductMedia")
    for media in ProductMedia.objects.exclude(attribute_value__isnull=True).iterator():
        media.attribute_values.add(media.attribute_value_id)


def copy_set_to_tag(apps, schema_editor):
    ProductMedia = apps.get_model("catalog", "ProductMedia")
    for media in ProductMedia.objects.prefetch_related("attribute_values"):
        values = sorted(media.attribute_values.all(), key=lambda v: str(v.pk))
        if values:
            media.attribute_value_id = values[0].pk
            media.save(update_fields=["attribute_value"])


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0018_category_label_paper"),
    ]

    operations = [
        migrations.AddField(
            model_name="productmedia",
            name="attribute_values",
            field=models.ManyToManyField(
                blank=True,
                related_name="tagged_media",
                to="catalog.attributevalue",
            ),
        ),
        migrations.RunPython(copy_tag_to_set, copy_set_to_tag),
    ]
