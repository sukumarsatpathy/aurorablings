"""
returns.services
~~~~~~~~~~~~~~~~

Public API:
═══════════

Return flow:
  1. create_return_request(order, user, items_data)
     ├─ policy_validation()   window check, eligibility, non-returnable
     ├─ build ReturnRequest + ReturnItems
     └─ log SUBMITTED

  2. approve_return(rr, changed_by, notes)       → APPROVED
     or
     reject_return(rr, changed_by, reason)       → REJECTED

  3. mark_items_received(rr, changed_by)         → ITEMS_RECEIVED

  4. inspect_items(rr, item_conditions, changed_by)
     ├─ record condition per item
     ├─ calculate_refund_amount()
     ├─ set is_refund_ready = True
     └─ → INSPECTED

  5. reintegrate_stock(rr, changed_by)
     ├─ inventory.process_return() per GOOD / MINOR_DAMAGE item
     └─ marks ReturnItem.stock_reintegrated = True

  6. initiate_refund(rr, changed_by)             → REFUND_INITIATED
  7. complete_return(rr, changed_by)             → COMPLETED

Exchange flow:
  1. create_exchange_request(order, user, items_data)
  2. approve_exchange / reject_exchange
  3. mark_items_received_exchange
  4. inspect_exchange_items + reintegrate_stock_exchange
  5. ship_exchange(exc, tracking, carrier)       → EXCHANGE_SHIPPED
  6. complete_exchange                           → COMPLETED
"""

from __future__ import annotations

from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from core.exceptions import ValidationError, ConflictError, NotFoundError
from core.logging import get_logger
from audit.models import ActorType, AuditAction
from audit.services.activity_logger import log_activity

from .models import (
    ReturnRequest, ReturnItem, ExchangeRequest, ExchangeItem,
    ReturnPolicy, ReturnStatusHistory,
    ReturnStatus, ExchangeStatus,
    RETURN_TRANSITIONS, EXCHANGE_TRANSITIONS,
    ReturnReason, ItemCondition,
)

logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────
#  Policy helpers
# ─────────────────────────────────────────────────────────────

def get_active_policy() -> ReturnPolicy | None:
    return ReturnPolicy.objects.filter(is_active=True).order_by("-created_at").first()


def validate_return_eligibility(
    order,
    item_ids: list,
    *,
    policy: ReturnPolicy | None = None,
    is_exchange: bool = False,
) -> None:
    """
    Raise ValidationError if the return/exchange is not allowed.

    Checks:
      1. Order status must be in policy.eligible_order_statuses
      2. Request must be within the return/exchange window (delivered_at + max days)
      3. None of the items can be from non-returnable categories
    """
    policy = policy or get_active_policy()
    if not policy:
        return   # No policy → allow everything (permissive default)

    # ── 1. Order status ───────────────────────────────────────
    eligible_statuses = policy.eligible_order_statuses or ["delivered", "completed"]
    if order.status not in eligible_statuses:
        raise ValidationError(
            f"Returns are only accepted for orders with status: {eligible_statuses}. "
            f"Order '{order.order_number}' is currently '{order.status}'."
        )

    # ── 2. Time window ────────────────────────────────────────
    reference_date = order.delivered_at or order.updated_at
    max_days       = policy.max_exchange_days if is_exchange else policy.max_return_days
    window_end     = reference_date + timezone.timedelta(days=max_days)

    if timezone.now() > window_end:
        kind = "exchange" if is_exchange else "return"
        raise ValidationError(
            f"The {kind} window of {max_days} days has expired. "
            f"Window closed on {window_end.date()}."
        )

    # ── 3. Non-returnable categories ──────────────────────────
    non_returnable = set(str(c) for c in (policy.non_returnable_category_ids or []))
    if non_returnable and item_ids:
        from apps.orders.models import OrderItem
        problem_items = (
            OrderItem.objects
            .filter(id__in=item_ids, variant__product__category_id__in=non_returnable)
            .select_related("variant__product__category")
        )
        if problem_items.exists():
            names = [i.product_name for i in problem_items]
            raise ValidationError(
                f"The following items are not eligible for return: {', '.join(names)}. "
                f"{policy.non_returnable_reason}"
            )


def _calculate_item_refund(item: ReturnItem, policy: ReturnPolicy | None) -> Decimal:
    """
    Compute refund amount for a single return item after inspection.

    Logic:
      - GOOD / MINOR_DAMAGE → full refund minus restocking fee
      - DAMAGED / MISSING_PARTS → 50% of item price
      - UNUSABLE → 0
    """
    base = item.unit_price * item.quantity
    condition = item.condition

    if condition in (ItemCondition.GOOD, ItemCondition.MINOR_DAMAGE):
        restocking_pct = (policy.restocking_fee_pct if policy else Decimal(0))
        refund = base * (1 - restocking_pct / 100)
    elif condition in (ItemCondition.DAMAGED, ItemCondition.MISSING_PARTS):
        refund = base * Decimal("0.5")
    else:  # UNUSABLE
        refund = Decimal("0")

    return refund.quantize(Decimal("0.01"))


# ─────────────────────────────────────────────────────────────
#  1.  Create Return Request
# ─────────────────────────────────────────────────────────────

@transaction.atomic
def create_return_request(
    *,
    order,
    user=None,
    items_data: list[dict],
    notes: str = "",
    pickup_address: dict | None = None,
) -> ReturnRequest:
    """
    items_data: [
        {
            "order_item_id": "uuid",
            "quantity": 2,
            "reason_code": "defective",
            "reason_detail": "...",
            "warehouse_id": "uuid"  # optional
        }
    ]
    """
    from apps.orders.models import OrderItem

    if not items_data:
        raise ValidationError("At least one item must be included in the return request.")

    item_ids = [d["order_item_id"] for d in items_data]
    policy   = get_active_policy()
    validate_return_eligibility(order, item_ids, policy=policy, is_exchange=False)

    rr = ReturnRequest.objects.create(
        order=order,
        user=user,
        status=ReturnStatus.SUBMITTED,
        notes=notes,
        pickup_address=pickup_address or order.shipping_address,
    )

    for data in items_data:
        order_item = OrderItem.objects.get(id=data["order_item_id"], order=order)
        warehouse  = None
        if data.get("warehouse_id"):
            from apps.inventory.selectors import get_warehouse_by_id
            warehouse = get_warehouse_by_id(data["warehouse_id"])

        ReturnItem.objects.create(
            return_request=rr,
            order_item=order_item,
            variant=order_item.variant,
            warehouse=warehouse or order_item.warehouse,
            quantity=data["quantity"],
            reason_code=data["reason_code"],
            reason_detail=data.get("reason_detail", ""),
            unit_price=order_item.unit_price,
        )

    _log_transition(rr=rr, to_status=ReturnStatus.SUBMITTED, changed_by=user)
    logger.info("return_request_created", return_number=rr.return_number, order=order.order_number)

    # Notify customer (async)
    try:
        from apps.notifications.tasks import trigger_event_task
        from apps.notifications.events import NotificationEvent
        trigger_event_task.delay(
            event=NotificationEvent.RETURN_SUBMITTED,
            context={"return_number": rr.return_number, "order_number": order.order_number,
                     "user_name": user.get_full_name() if user else "Customer"},
            user_id=str(user.id) if user else None,
        )
    except Exception:
        pass

    return rr


# ─────────────────────────────────────────────────────────────
#  2a.  Approve / Reject Return
# ─────────────────────────────────────────────────────────────

@transaction.atomic
def approve_return(*, rr: ReturnRequest, changed_by=None, notes: str = "") -> ReturnRequest:
    rr = _transition_return(rr, ReturnStatus.UNDER_REVIEW, changed_by, "Request being reviewed.")
    rr = _transition_return(rr, ReturnStatus.APPROVED, changed_by, notes or "Return approved.")
    rr.approved_at = timezone.now()
    rr.save(update_fields=["approved_at"])
    logger.info("return_approved", return_number=rr.return_number)

    try:
        from apps.notifications.tasks import trigger_event_task
        from apps.notifications.events import NotificationEvent
        trigger_event_task.delay(
            event=NotificationEvent.RETURN_APPROVED,
            context={"return_number": rr.return_number, "order_number": rr.order.order_number,
                     "user_name": rr.user.get_full_name() if rr.user else "Customer"},
            user_id=str(rr.user.id) if rr.user else None,
        )
    except Exception:
        pass

    return rr


@transaction.atomic
def reject_return(*, rr: ReturnRequest, changed_by=None, reason: str = "") -> ReturnRequest:
    rr = _transition_return(rr, ReturnStatus.REJECTED, changed_by, reason)
    rr.rejection_reason = reason
    rr.save(update_fields=["rejection_reason"])
    logger.info("return_rejected", return_number=rr.return_number, reason=reason)
    return rr


# ─────────────────────────────────────────────────────────────
#  3.  Mark Items Received
# ─────────────────────────────────────────────────────────────

@transaction.atomic
def mark_items_received(
    *,
    rr: ReturnRequest,
    tracking_no: str = "",
    carrier: str = "",
    changed_by=None,
) -> ReturnRequest:
    rr.return_tracking_no = tracking_no
    rr.return_carrier     = carrier
    rr.items_received_at  = timezone.now()
    rr.save(update_fields=["return_tracking_no", "return_carrier", "items_received_at"])
    return _transition_return(rr, ReturnStatus.ITEMS_RECEIVED, changed_by, "Items received at warehouse.")


# ─────────────────────────────────────────────────────────────
#  4.  Inspect Items  (sets condition + calculates refund)
# ─────────────────────────────────────────────────────────────

@transaction.atomic
def inspect_return_items(
    *,
    rr: ReturnRequest,
    item_conditions: list[dict],
    changed_by=None,
    staff_notes: str = "",
) -> ReturnRequest:
    """
    item_conditions: [
        { "item_id": "uuid", "condition": "good" | "damaged" | ... }
    ]

    Calculates per-item and total refund amounts.
    Sets rr.is_refund_ready = True on success.
    """
    policy  = get_active_policy()
    cond_map = {str(d["item_id"]): d["condition"] for d in item_conditions}
    total_refund = Decimal("0")
    total_restocking = Decimal("0")

    for item in rr.items.select_related("order_item"):
        condition = cond_map.get(str(item.id), ItemCondition.GOOD)
        item.condition   = condition
        refund_amt       = _calculate_item_refund(item, policy)
        item.refund_amount = refund_amt
        item.save(update_fields=["condition", "refund_amount"])

        total_refund     += refund_amt

        if condition in (ItemCondition.GOOD, ItemCondition.MINOR_DAMAGE) and policy:
            base = item.unit_price * item.quantity
            total_restocking += (base - refund_amt)

    rr.refund_amount          = total_refund
    rr.restocking_fee_applied = total_restocking
    rr.is_refund_ready        = True
    rr.staff_notes            = staff_notes
    rr.inspected_at           = timezone.now()
    rr.save(update_fields=[
        "refund_amount", "restocking_fee_applied", "is_refund_ready", "staff_notes", "inspected_at"
    ])

    return _transition_return(
        rr, ReturnStatus.INSPECTED, changed_by,
        f"Inspection done. Refund: {total_refund}. Restocking fee: {total_restocking}."
    )


# ─────────────────────────────────────────────────────────────
#  5.  Reintegrate Stock
# ─────────────────────────────────────────────────────────────

@transaction.atomic
def reintegrate_stock_for_return(*, rr: ReturnRequest, changed_by=None) -> ReturnRequest:
    """
    Push returned inventory back into the warehouse.
    Only GOOD and MINOR_DAMAGE items are reintegrated to sellable stock.
    DAMAGED items go to quarantine (handled by inventory.process_return).
    """
    from apps.inventory.services import process_return

    REINTEGRATE_CONDITIONS = {ItemCondition.GOOD, ItemCondition.MINOR_DAMAGE}

    for item in rr.items.filter(stock_reintegrated=False).select_related("variant", "warehouse"):
        if not item.variant or not item.warehouse:
            continue

        to_stock = item.condition in REINTEGRATE_CONDITIONS

        process_return(
            variant_id=item.variant.id,
            warehouse_id=item.warehouse.id,
            quantity=item.quantity,
            return_to_stock=to_stock,
            return_id=str(rr.id),
            notes=f"Return {rr.return_number} — condition: {item.condition}",
            created_by=changed_by,
        )
        item.stock_reintegrated = True
        item.save(update_fields=["stock_reintegrated"])

    logger.info("return_stock_reintegrated", return_number=rr.return_number)
    return rr


# ─────────────────────────────────────────────────────────────
#  6.  Initiate Refund  +  7. Complete
# ─────────────────────────────────────────────────────────────

@transaction.atomic
def initiate_refund_for_return(*, rr: ReturnRequest, changed_by=None) -> ReturnRequest:
    if not rr.is_refund_ready:
        raise ConflictError("Return must be inspected before initiating a refund.")

    rr.refund_initiated_at = timezone.now()
    rr.save(update_fields=["refund_initiated_at"])
    rr = _transition_return(
        rr, ReturnStatus.REFUND_INITIATED, changed_by,
        f"Refund of {rr.refund_amount} initiated."
    )
    logger.info(
        "return_refund_initiated",
        return_number=rr.return_number,
        amount=str(rr.refund_amount),
    )
    return rr


@transaction.atomic
def complete_return(*, rr: ReturnRequest, changed_by=None) -> ReturnRequest:
    rr.completed_at = timezone.now()
    rr.save(update_fields=["completed_at"])
    return _transition_return(rr, ReturnStatus.COMPLETED, changed_by, "Return completed.")


@transaction.atomic
def reject_after_inspection(*, rr: ReturnRequest, reason: str, changed_by=None) -> ReturnRequest:
    rr.rejection_reason = reason
    rr.is_refund_ready  = False
    rr.save(update_fields=["rejection_reason", "is_refund_ready"])
    return _transition_return(rr, ReturnStatus.REJECTED_AFTER_INSPECTION, changed_by, reason)


# ─────────────────────────────────────────────────────────────
#  Exchange: Create
# ─────────────────────────────────────────────────────────────

@transaction.atomic
def create_exchange_request(
    *,
    order,
    user=None,
    items_data: list[dict],
    shipping_address: dict | None = None,
    notes: str = "",
) -> ExchangeRequest:
    """
    items_data: [
        {
            "order_item_id": "uuid",
            "replacement_variant_id": "uuid",
            "quantity": 1,
            "reason_code": "size_issue",
            "reason_detail": "..."
        }
    ]
    """
    from apps.orders.models import OrderItem
    from apps.catalog.models import ProductVariant

    if not items_data:
        raise ValidationError("At least one item must be included in the exchange request.")

    item_ids = [d["order_item_id"] for d in items_data]
    policy   = get_active_policy()
    validate_return_eligibility(order, item_ids, policy=policy, is_exchange=True)

    exc = ExchangeRequest.objects.create(
        order=order,
        user=user,
        status=ExchangeStatus.SUBMITTED,
        notes=notes,
        shipping_address=shipping_address or order.shipping_address,
    )

    for data in items_data:
        order_item          = OrderItem.objects.get(id=data["order_item_id"], order=order)
        replacement_variant = ProductVariant.objects.get(id=data["replacement_variant_id"])

        price_diff = replacement_variant.price - order_item.unit_price

        ExchangeItem.objects.create(
            exchange_request=exc,
            order_item=order_item,
            original_variant=order_item.variant,
            replacement_variant=replacement_variant,
            warehouse=order_item.warehouse,
            quantity=data["quantity"],
            reason_code=data["reason_code"],
            reason_detail=data.get("reason_detail", ""),
            price_difference=price_diff,
        )

    _log_transition(exc=exc, to_status=ExchangeStatus.SUBMITTED, changed_by=user)
    logger.info("exchange_request_created", exchange_number=exc.exchange_number)
    return exc


# ─────────────────────────────────────────────────────────────
#  Exchange: Status transitions
# ─────────────────────────────────────────────────────────────

@transaction.atomic
def approve_exchange(*, exc: ExchangeRequest, changed_by=None, notes: str = "") -> ExchangeRequest:
    exc = _transition_exchange(exc, ExchangeStatus.UNDER_REVIEW, changed_by)
    exc = _transition_exchange(exc, ExchangeStatus.APPROVED, changed_by, notes or "Exchange approved.")
    exc.approved_at = timezone.now()
    exc.save(update_fields=["approved_at"])
    return exc


@transaction.atomic
def reject_exchange(*, exc: ExchangeRequest, reason: str = "", changed_by=None) -> ExchangeRequest:
    exc.rejection_reason = reason
    exc.save(update_fields=["rejection_reason"])
    return _transition_exchange(exc, ExchangeStatus.REJECTED, changed_by, reason)


@transaction.atomic
def mark_exchange_items_received(
    *, exc: ExchangeRequest, tracking_no: str = "", carrier: str = "", changed_by=None,
) -> ExchangeRequest:
    exc.return_tracking_no = tracking_no
    exc.return_carrier     = carrier
    exc.items_received_at  = timezone.now()
    exc.save(update_fields=["return_tracking_no", "return_carrier", "items_received_at"])
    return _transition_exchange(exc, ExchangeStatus.ITEMS_RECEIVED, changed_by, "Items received.")


@transaction.atomic
def inspect_exchange_items(
    *,
    exc: ExchangeRequest,
    item_conditions: list[dict],
    changed_by=None,
) -> ExchangeRequest:
    cond_map = {str(d["item_id"]): d["condition"] for d in item_conditions}
    for item in exc.items.all():
        item.condition = cond_map.get(str(item.id), ItemCondition.GOOD)
        item.save(update_fields=["condition"])

    # Reserve replacement stock
    from apps.inventory.services import reserve_stock
    for item in exc.items.filter(replacement_variant__isnull=False).select_related("replacement_variant", "warehouse"):
        reserve_stock(
            variant_id=item.replacement_variant.id,
            warehouse_id=item.warehouse.id if item.warehouse else None,
            quantity=item.quantity,
            order_id=str(exc.order.id),
            notes=f"Exchange {exc.exchange_number} — replacement reservation",
            created_by=changed_by,
        )

    exc.inspected_at = timezone.now()
    exc.save(update_fields=["inspected_at"])
    return _transition_exchange(exc, ExchangeStatus.INSPECTED, changed_by, "Inspection complete.")


@transaction.atomic
def reintegrate_stock_for_exchange(*, exc: ExchangeRequest, changed_by=None) -> ExchangeRequest:
    from apps.inventory.services import process_exchange
    for item in exc.items.filter(
        stock_reintegrated=False,
        original_variant__isnull=False,
        replacement_variant__isnull=False,
    ).select_related("original_variant", "replacement_variant", "warehouse"):
        process_exchange(
            exchange_id=str(exc.id),
            warehouse_id=item.warehouse.id if item.warehouse else None,
            outgoing_variant_id=item.replacement_variant.id,  # we send replacement to customer
            outgoing_quantity=item.quantity,
            incoming_variant_id=item.original_variant.id,     # customer returns original
            incoming_quantity=item.quantity,
            notes=f"Exchange {exc.exchange_number}",
            created_by=changed_by,
        )
        item.stock_reintegrated = True
        item.save(update_fields=["stock_reintegrated"])
    return exc


@transaction.atomic
def ship_exchange(
    *, exc: ExchangeRequest, tracking_no: str = "", carrier: str = "", changed_by=None,
) -> ExchangeRequest:
    exc.exchange_tracking_no = tracking_no
    exc.exchange_carrier     = carrier
    exc.exchange_shipped_at  = timezone.now()
    exc.save(update_fields=["exchange_tracking_no", "exchange_carrier", "exchange_shipped_at"])
    return _transition_exchange(
        exc, ExchangeStatus.EXCHANGE_SHIPPED, changed_by,
        f"Exchange shipped via {carrier}. Tracking: {tracking_no}"
    )


@transaction.atomic
def complete_exchange(*, exc: ExchangeRequest, changed_by=None) -> ExchangeRequest:
    exc.completed_at = timezone.now()
    exc.save(update_fields=["completed_at"])
    return _transition_exchange(exc, ExchangeStatus.COMPLETED, changed_by, "Exchange completed.")


@transaction.atomic
def update_return_request(*, rr: ReturnRequest, **fields) -> ReturnRequest:
    mutable_fields = {"notes", "staff_notes", "pickup_address", "return_tracking_no", "return_carrier"}
    for key, value in fields.items():
        if key in mutable_fields:
            setattr(rr, key, value)
    rr.save()
    return rr


@transaction.atomic
def update_exchange_request(*, exc: ExchangeRequest, **fields) -> ExchangeRequest:
    mutable_fields = {
        "notes", "staff_notes", "shipping_address",
        "return_tracking_no", "return_carrier",
        "exchange_tracking_no", "exchange_carrier",
    }
    for key, value in fields.items():
        if key in mutable_fields:
            setattr(exc, key, value)
    exc.save()
    return exc


@transaction.atomic
def delete_return_request(*, rr: ReturnRequest) -> None:
    if rr.status not in {ReturnStatus.SUBMITTED, ReturnStatus.UNDER_REVIEW, ReturnStatus.REJECTED}:
        raise ConflictError("Only submitted/review/rejected returns can be deleted.")
    rr.delete()


@transaction.atomic
def delete_exchange_request(*, exc: ExchangeRequest) -> None:
    if exc.status not in {ExchangeStatus.SUBMITTED, ExchangeStatus.UNDER_REVIEW, ExchangeStatus.REJECTED}:
        raise ConflictError("Only submitted/review/rejected exchanges can be deleted.")
    exc.delete()


# ─────────────────────────────────────────────────────────────
#  Private: transition guards + history logging
# ─────────────────────────────────────────────────────────────

def _transition_return(
    rr: ReturnRequest, new_status: str, changed_by=None, notes: str = ""
) -> ReturnRequest:
    if not rr.can_transition_to(new_status):
        raise ConflictError(
            f"Invalid return transition: '{rr.status}' → '{new_status}' "
            f"for {rr.return_number}."
        )
    old = rr.status
    rr.status = new_status
    rr.save(update_fields=["status", "updated_at"])
    _log_transition(rr=rr, from_status=old, to_status=new_status, changed_by=changed_by, notes=notes)
    logger.info(
        "return_status_changed",
        return_number=rr.return_number,
        from_status=old, to_status=new_status,
    )
    log_activity(
        user=changed_by,
        actor_type=(
            ActorType.ADMIN
            if getattr(changed_by, "role", "") == "admin"
            else ActorType.STAFF
            if getattr(changed_by, "role", "") == "staff"
            else ActorType.SYSTEM
        ),
        action=AuditAction.STATUS_CHANGE,
        entity_type="return_request",
        entity_id=str(rr.id),
        description=f"Return {rr.return_number} moved from {old} to {new_status}",
        metadata={"return_number": rr.return_number, "from_status": old, "to_status": new_status, "notes": notes},
    )
    return rr


def _transition_exchange(
    exc: ExchangeRequest, new_status: str, changed_by=None, notes: str = ""
) -> ExchangeRequest:
    if not exc.can_transition_to(new_status):
        raise ConflictError(
            f"Invalid exchange transition: '{exc.status}' → '{new_status}' "
            f"for {exc.exchange_number}."
        )
    old = exc.status
    exc.status = new_status
    exc.save(update_fields=["status", "updated_at"])
    _log_transition(exc=exc, from_status=old, to_status=new_status, changed_by=changed_by, notes=notes)
    log_activity(
        user=changed_by,
        actor_type=(
            ActorType.ADMIN
            if getattr(changed_by, "role", "") == "admin"
            else ActorType.STAFF
            if getattr(changed_by, "role", "") == "staff"
            else ActorType.SYSTEM
        ),
        action=AuditAction.STATUS_CHANGE,
        entity_type="exchange_request",
        entity_id=str(exc.id),
        description=f"Exchange {exc.exchange_number} moved from {old} to {new_status}",
        metadata={"exchange_number": exc.exchange_number, "from_status": old, "to_status": new_status, "notes": notes},
    )
    return exc


def _log_transition(
    *,
    rr: ReturnRequest | None = None,
    exc: ExchangeRequest | None = None,
    from_status: str = "",
    to_status: str,
    changed_by=None,
    notes: str = "",
) -> None:
    ReturnStatusHistory.objects.create(
        return_request=rr,
        exchange_request=exc,
        from_status=from_status,
        to_status=to_status,
        changed_by=changed_by,
        notes=notes,
    )
