"""
Put quick items back on the shelf when their sale is cancelled.

A signal rather than a call in each cancel path, because there are several — a
POS void, "back to cart", the stale-order sweeper, an admin cancelling from the
dashboard — and the orders app should not need to know quick items exist. The
handler does nothing for an order without quick lines, and restocking is
idempotent, so a second save of a cancelled order cannot double the count.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.orders.models import Order, OrderStatus


@receiver(post_save, sender=Order, dispatch_uid="pos_restock_quick_items_on_cancel")
def restock_quick_items_on_cancel(sender, instance: Order, **kwargs):
    if instance.status != OrderStatus.CANCELLED:
        return
    from apps.pos.models import POSQuickSaleLine

    if not POSQuickSaleLine.objects.filter(order_id=instance.pk, restocked_at__isnull=True).exists():
        return
    from apps.pos.quick_items import restock_order

    restock_order(instance)
