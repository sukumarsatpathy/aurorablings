from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0009_productvariant_allow_backorder"),
    ]

    operations = [
        migrations.AddField(
            model_name="productmedia",
            name="image_large",
            field=models.ImageField(blank=True, null=True, upload_to="products/%Y/%m/"),
        ),
        migrations.AddField(
            model_name="productmedia",
            name="image_medium",
            field=models.ImageField(blank=True, null=True, upload_to="products/%Y/%m/"),
        ),
        migrations.AddField(
            model_name="productmedia",
            name="image_small",
            field=models.ImageField(blank=True, null=True, upload_to="products/%Y/%m/"),
        ),
    ]

