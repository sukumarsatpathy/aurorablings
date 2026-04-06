from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0013_alter_notification_event_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="NewsletterSubscriber",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("email", models.EmailField(max_length=254, unique=True, db_index=True)),
                ("source", models.CharField(blank=True, default="footer", max_length=50)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("subscribed_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-subscribed_at"],
            },
        ),
        migrations.AddIndex(
            model_name="newslettersubscriber",
            index=models.Index(fields=["is_active", "subscribed_at"], name="notificatio_is_acti_ce3fd7_idx"),
        ),
    ]
