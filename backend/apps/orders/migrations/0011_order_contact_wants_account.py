"""
Whether the counter customer agreed to an account.

Kept apart from the email itself. The till used to send the email only when the
account box was ticked, which meant an address given purely so a receipt could
be sent was discarded — the sale then had no way to reach the customer at all.
Now the email is always kept and this records the separate decision.

Defaults True so existing rows keep today's behaviour: every order created
before this point sent its email only when an account was wanted.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0010_alter_order_payment_method"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="contact_wants_account",
            field=models.BooleanField(
                default=True,
                help_text=(
                    "Did the customer agree to an account being created? Kept apart "
                    "from the email itself: the email is needed for the receipt "
                    "whatever they decided, and a receipt is transactional. An "
                    "existing account is still linked either way — declining means "
                    "no NEW account, not no record."
                ),
            ),
        ),
    ]
