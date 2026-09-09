"""
Backfill the tender ledger from history.

Every order that is already PAID gets exactly one CAPTURED ``ONLINE`` tender for
its ``grand_total``, so that ``amount_paid(order)`` is correct for orders placed
before the ledger existed.  Without this, every historical order looks unpaid to
the new code and ``derive_payment_status`` would try to walk them backwards.

Deliberately conservative:
  * only PAID orders are touched — pending, failed, cancelled and refunded orders
    are left alone, since their true tender history is unknown and inventing one
    would be worse than having none.
  * ``provider_ref`` is left blank rather than guessed from PaymentTransaction.
    A wrong ref would collide with a future live webhook on the unique
    constraint; a blank one is excluded from that constraint by design.
  * idempotent — orders that already have a tender are skipped, so a re-run
    after a partial failure is safe.
  * fully reversible: the reverse only deletes rows this migration would create.
"""

from decimal import Decimal

from django.db import migrations

BACKFILL_NOTE = "backfilled from order history"


def backfill(apps, schema_editor):
    Order = apps.get_model("orders", "Order")
    OrderTender = apps.get_model("payments", "OrderTender")

    paid_without_tenders = (
        Order.objects.filter(payment_status="paid")
        .exclude(tenders__isnull=False)
        .only("id", "grand_total", "currency")
        .iterator(chunk_size=500)
    )

    batch, created = [], 0
    for order in paid_without_tenders:
        total = order.grand_total or Decimal("0.00")
        if total <= Decimal("0.00"):
            # A zero-value paid order (fully discounted, or bad legacy data) has
            # nothing to tender. The check constraint forbids a zero row anyway.
            continue
        batch.append(
            OrderTender(
                order_id=order.id,
                method="online",
                status="captured",
                amount_applied=total,
                currency=order.currency or "INR",
                notes=BACKFILL_NOTE,
                raw={},
            )
        )
        if len(batch) >= 500:
            OrderTender.objects.bulk_create(batch)
            created += len(batch)
            batch = []

    if batch:
        OrderTender.objects.bulk_create(batch)
        created += len(batch)

    print(f"  backfilled {created} tender(s) from paid orders")


def unbackfill(apps, schema_editor):
    OrderTender = apps.get_model("payments", "OrderTender")
    deleted, _ = OrderTender.objects.filter(notes=BACKFILL_NOTE).delete()
    print(f"  removed {deleted} backfilled tender(s)")


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0006_ordertender"),
    ]

    operations = [
        migrations.RunPython(backfill, unbackfill),
    ]
