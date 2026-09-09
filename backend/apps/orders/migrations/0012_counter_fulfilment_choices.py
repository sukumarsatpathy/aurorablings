"""
Two new choices, so a counter sale can describe itself honestly.

`shipping_approval_status` gains NOT_REQUIRED. Carry-away sales were being
marked REJECTED to keep them out of the approval queue — effective, but it
reads in the admin as though somebody refused to ship the order. Rejected is a
decision; a handover is the absence of the question.

`fulfillment_method` gains COUNTER, so a stall sale is not "Unassigned" for
ever, waiting for a courier that is never coming.

Choices-only: no column is added or altered, and existing rows are untouched.
Historical POS orders keep REJECTED / UNASSIGNED, which still display and still
stay out of the queue; only new sales use the new values.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0011_order_contact_wants_account"),
    ]

    operations = [
        migrations.AlterField(
            model_name="order",
            name="shipping_approval_status",
            field=models.CharField(
                choices=[
                    ("pending_shipping_approval", "Pending Shipping Approval"),
                    ("approved", "Approved"),
                    ("rejected", "Rejected"),
                    ("not_required", "Not required — handed over"),
                ],
                db_index=True,
                default="pending_shipping_approval",
                max_length=40,
            ),
        ),
        migrations.AlterField(
            model_name="order",
            name="fulfillment_method",
            field=models.CharField(
                choices=[
                    ("unassigned", "Unassigned"),
                    ("counter", "Handed over at the counter"),
                    ("local_delivery", "Local Delivery"),
                    ("nimbuspost", "NimbusPost"),
                    ("shiprocket", "Shiprocket"),
                ],
                db_index=True,
                default="unassigned",
                max_length=30,
            ),
        ),
    ]
