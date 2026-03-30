from celery import shared_task

from core.logging import get_logger

logger = get_logger(__name__)


@shared_task(
    bind=True,
    max_retries=5,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=1800,
    retry_jitter=True,
    name="shipping.create_shipment_for_order",
)
def create_shipment_for_order(self, order_id: str):
    from . import services

    try:
        shipment = services.create_or_update_shipment_for_order(order_id=order_id)
        logger.info("create_shipment_for_order_ok", order_id=order_id, shipment_id=str(shipment.id))
        return str(shipment.id)
    except Exception as exc:
        logger.warning("create_shipment_for_order_failed", order_id=order_id, error=str(exc))
        raise


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=120,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=3600,
    retry_jitter=True,
    name="shipping.retry_create_shipment",
)
def retry_create_shipment(self, order_id: str):
    from . import services

    shipment = services.create_or_update_shipment_for_order(order_id=order_id, source="manual", force=True)
    logger.info("retry_create_shipment_ok", order_id=order_id, shipment_id=str(shipment.id))
    return str(shipment.id)


@shared_task(
    bind=True,
    max_retries=5,
    default_retry_delay=120,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=1800,
    retry_jitter=True,
    name="shipping.sync_tracking_for_shipment",
)
def sync_tracking_for_shipment(self, shipment_id: str):
    from . import services

    shipment = services.sync_tracking(shipment_id=shipment_id)
    logger.info("sync_tracking_for_shipment_ok", shipment_id=shipment_id, status=shipment.status)
    return shipment.status


@shared_task(
    bind=True,
    max_retries=5,
    default_retry_delay=30,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    name="shipping.process_shiprocket_webhook_event",
)
def process_shiprocket_webhook_event(self, event_id: str):
    from . import services

    event = services.process_webhook_event(event_id)
    logger.info("process_shiprocket_webhook_event_ok", event_id=event_id, shipment_id=str(event.shipment_id or ""))
    return str(event.shipment_id or "")


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=900,
    retry_jitter=True,
    name="shipping.request_pickup_for_shipment",
)
def request_pickup_for_shipment(self, shipment_id: str):
    from . import services

    shipment = services.request_pickup_for_shipment(shipment_id=shipment_id)
    logger.info("request_pickup_for_shipment_ok", shipment_id=shipment_id)
    return str(shipment.id)


@shared_task(name="shipping.refresh_shiprocket_token")
def refresh_shiprocket_token():
    from . import services

    ok = services.refresh_provider_token()
    logger.info("refresh_shiprocket_token", success=ok)
    return ok


@shared_task(name="shipping.reconcile_stuck_shipments")
def reconcile_stuck_shipments():
    from . import services

    processed = services.reconcile_stuck_shipments()
    logger.info("reconcile_stuck_shipments", processed=processed)
    return processed
