import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0003_rename_notificatio_product_9ca498_idx_notificatio_product_0650fc_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="notificationtemplate",
            name="key",
            field=models.CharField(blank=True, db_index=True, max_length=100, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="notificationtemplate",
            name="template_file",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="notificationtemplate",
            name="description",
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name="notificationtemplate",
            name="event",
            field=models.CharField(blank=True, db_index=True, max_length=100, choices=[("order.created", "order.created"), ("order.shipped", "order.shipped"), ("order.delivered", "order.delivered"), ("user.forgot_password", "user.forgot_password"), ("user.blocked", "user.blocked"), ("contact.form.submitted", "contact.form.submitted"), ("product.notify_me", "product.notify_me")]),
        ),
        migrations.AlterField(
            model_name="notification",
            name="event",
            field=models.CharField(blank=True, db_index=True, max_length=100, choices=[("order.created", "order.created"), ("order.shipped", "order.shipped"), ("order.delivered", "order.delivered"), ("user.forgot_password", "user.forgot_password"), ("user.blocked", "user.blocked"), ("contact.form.submitted", "contact.form.submitted"), ("product.notify_me", "product.notify_me")]),
        ),
        migrations.AddField(
            model_name="notification",
            name="email",
            field=models.EmailField(blank=True, max_length=254),
        ),
        migrations.AddField(
            model_name="notification",
            name="event_type",
            field=models.CharField(blank=True, db_index=True, max_length=100),
        ),
        migrations.AddField(
            model_name="notification",
            name="payload",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="notification",
            name="error_message",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="notification",
            name="subject_snapshot",
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name="notification",
            name="template_key",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.CreateModel(
            name="NotificationAttempt",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("attempt_no", models.PositiveSmallIntegerField(default=1)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("sent", "Sent"), ("failed", "Failed"), ("skipped", "Skipped")], max_length=15)),
                ("error_message", models.TextField(blank=True)),
                ("provider_response", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("notification", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="attempts", to="notifications.notification")),
            ],
            options={"ordering": ["created_at"], "unique_together": {("notification", "attempt_no")}},
        ),
    ]
