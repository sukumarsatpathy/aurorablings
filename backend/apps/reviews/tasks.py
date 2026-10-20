from celery import shared_task

from .services import recalculate_product_review_stats


@shared_task(name="reviews.recalculate_product_review_stats")
def recalculate_product_review_stats_task(product_id: str) -> None:
    recalculate_product_review_stats(product_id=product_id)


@shared_task(name="reviews.send_post_delivery_review_reminders")
def send_post_delivery_review_reminders_task() -> dict:
    """Daily: ask customers to review what was delivered a few days ago (see reviews.reminders)."""
    from .reminders import send_post_delivery_review_reminders

    return send_post_delivery_review_reminders()
