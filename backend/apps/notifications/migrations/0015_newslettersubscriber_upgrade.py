from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0014_newslettersubscriber"),
    ]

    operations = [
        migrations.AddField(
            model_name="newslettersubscriber",
            name="confirmation_email_sent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="newslettersubscriber",
            name="confirmation_token",
            field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True),
        ),
        migrations.AddField(
            model_name="newslettersubscriber",
            name="confirmed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="newslettersubscriber",
            name="is_confirmed",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name="newslettersubscriber",
            name="unsubscribe_token",
            field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True),
        ),
        migrations.AddField(
            model_name="newslettersubscriber",
            name="unsubscribed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="newslettersubscriber",
            name="welcome_email_sent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddIndex(
            model_name="newslettersubscriber",
            index=models.Index(fields=["is_confirmed", "subscribed_at"], name="notificatio_is_conf_8a238a_idx"),
        ),
    ]
