from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0019_product_media_attribute_values"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="productmedia",
            name="attribute_value",
        ),
    ]
