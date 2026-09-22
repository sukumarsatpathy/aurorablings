"""
pos.order_service
~~~~~~~~~~~~~~~~~

Ringing up a sale.

This deliberately does not reimplement ordering. `orders.services` already turns a
list of items into a real order with stock reserved, coupons validated and pricing
run — the counter uses that same path, so a POS sale and a website sale cannot
drift apart in what they cost or what they reserve.

What is POS-specific is added around it: counter attribution, the manual discount
with its ceiling, and the fulfilment branch that keeps a carried-away sale out of
the courier pipeline.

The rule the whole module exists to enforce: **the tablet never sends a price.**
It sends variant ids and quantities and, at most, a requested discount. Every
figure is computed here. A counter device is shared, unlocked, and handled by
whoever is standing at the stall.
"""

from __future__ import annotations

from decimal import Decimal

import structlog
from django.conf import settings
from django.db import transaction

from apps.orders import services as order_services
from apps.orders.models import (
    FulfilmentType, FulfillmentMethod, Order, PaymentMethod, PaymentStatus,
    ShippingApprovalStatus,
)
from apps.pos.models import POSShift
from apps.pos.services import attach_to_counter

logger = structlog.get_logger(__name__)

ZERO = Decimal("0.00")

#: Percent a sales staff member may discount without a manager. Tunable; the
#: control is that the ceiling is enforced here rather than in the UI.
DEFAULT_DISCOUNT_CEILING_PCT = Decimal("10")

#: Free text is not reportable. A short fixed list is.
DISCOUNT_REASONS = (
    "display_piece",
    "minor_defect",
    "bulk_purchase",
    "repeat_customer",
    "price_match",
)


class POSOrderError(Exception):
    """Raised when a counter sale cannot be created or altered as asked."""


def discount_ceiling_pct() -> Decimal:
    return Decimal(str(getattr(settings, "POS_DISCOUNT_CEILING_PCT", DEFAULT_DISCOUNT_CEILING_PCT)))


def quote(
    *,
    items: list[dict],
    coupon_code: str = "",
    fulfilment_type: str = FulfilmentType.CARRY_AWAY,
) -> dict:
    """
    Price a cart without persisting anything — what the counter shows while the
    customer is still deciding. Same pricing engine as checkout.

    Carry-away drops the shipping line the same way create_pos_order does. A
    quote that disagrees with the sale it turns into is worse than no quote:
    staff read the figure out loud before the order exists.
    """
    priced = order_services.calculate_admin_order_pricing(
        items=items, coupon_code=(coupon_code or "").strip(),
    )

    if fulfilment_type == FulfilmentType.CARRY_AWAY:
        shipping = Decimal(str(priced.get("shipping_cost") or 0))
        if shipping:
            total = Decimal(str(priced.get("grand_total") or 0)) - shipping
            # Decimal in, Decimal out — the caller serialises. Handing back a
            # string for one key and a Decimal for the rest is how arithmetic
            # further up quietly becomes string concatenation.
            priced["grand_total"] = total.quantize(Decimal("0.01"))
            priced["shipping_cost"] = Decimal("0.00")

    return priced


@transaction.atomic
def create_pos_order(
    *,
    items: list[dict],
    shift: POSShift,
    staff,
    contact_name: str = "",
    contact_phone: str = "",
    contact_email: str = "",
    contact_date_of_birth=None,
    contact_anniversary_date=None,
    create_account: bool = True,
    coupon_code: str = "",
    fulfilment_type: str = FulfilmentType.CARRY_AWAY,
    shipping_address: dict | None = None,
    notes: str = "",
) -> Order:
    """
    Create a counter sale, unpaid, ready to take money against.

    Carry-away is the default because that is what a stall does. A ship-to
    customer order needs an address, and is refused without one rather than
    silently becoming a sale nobody can deliver.
    """
    if not shift.is_open:
        raise POSOrderError("Cannot ring up a sale on a closed shift.")
    if not items:
        raise POSOrderError("A sale needs at least one item.")

    if fulfilment_type == FulfilmentType.SHIP and not (shipping_address or {}):
        raise POSOrderError("A ship-to-customer sale needs a delivery address.")

    order = order_services.create_admin_order_from_items(
        items=items,
        guest_email=contact_email or "",
        shipping_address=shipping_address or {},
        payment_method=PaymentMethod.UPI,
        coupon_code=(coupon_code or "").strip(),
        notes=notes,
        changed_by=staff,
    )

    order.contact_name = (contact_name or "").strip()
    order.contact_phone = (contact_phone or "").strip()
    order.fulfilment_type = fulfilment_type
    # The email is on the order either way — a receipt is transactional and needs
    # somewhere to go. This flag is the separate question of whether they wanted
    # an account, and it is what the post-settlement task honours.
    order.contact_wants_account = bool(create_account and (contact_email or "").strip())
    # Parked here until the post-settlement task knows whose sale this is.
    order.contact_date_of_birth = contact_date_of_birth
    order.contact_anniversary_date = contact_anniversary_date

    fields = [
        "contact_name", "contact_phone", "fulfilment_type", "contact_wants_account",
        "contact_date_of_birth", "contact_anniversary_date",
    ]

    if fulfilment_type == FulfilmentType.CARRY_AWAY:
        # The customer is walking out with it. Leaving this pending would park
        # every stall sale in the shipping-approval queue forever, and the queue
        # is only useful if everything in it actually needs a decision.
        order.shipping_approval_status = ShippingApprovalStatus.NOT_REQUIRED
        order.shipping_approval_notes = "Carried away from the counter — no shipment required."
        order.fulfillment_method = FulfillmentMethod.COUNTER
        fields += [
            "shipping_approval_status", "shipping_approval_notes", "fulfillment_method",
        ]

        if order.shipping_cost:
            # And nobody is shipping it, so nobody may be charged for shipping.
            #
            # The surcharge engine prices every order as a delivery, because until
            # now every order was one. Its free-above-threshold rule lands a flat
            # rate on any sale under the threshold — which at a stall is most of
            # them. The customer is standing at the counter watching the screen,
            # so this is not a rounding error they will forgive.
            #
            # Only shipping is removed. Tax still applies to a counter sale.
            order.grand_total = (order.grand_total - order.shipping_cost).quantize(Decimal("0.01"))
            order.shipping_cost = Decimal("0.00")
            fields += ["shipping_cost", "grand_total"]

    order.save(update_fields=fields)
    attach_to_counter(order=order, shift=shift, staff=staff)

    logger.info(
        "pos_order_created",
        order_id=str(order.id), order_number=order.order_number,
        terminal=shift.terminal.code, staff=getattr(staff, "id", None),
        fulfilment=fulfilment_type, total=str(order.grand_total),
    )
    return order


@transaction.atomic
def apply_manual_discount(
    *,
    order: Order,
    amount: Decimal | None = None,
    percent: Decimal | None = None,
    reason: str,
    staff,
    approved_by=None,
) -> Order:
    """
    Take money off a sale, on a staff member's say-so, with a paper trail.

    Three guards, in order of how expensive they are to have missed:

    1. **Not after money has arrived.** Discounting a part-paid sale would change
       the total under a tender that has already settled against it, and the
       ledger would be right while the order was wrong.
    2. **Ceiling enforced here.** The UI asks for a manager PIN past 10%, but the
       UI runs on a shared tablet at a stall. This is the copy that counts.
    3. **A reason from a fixed list.** Free text cannot be reported on, and the
       report is the entire point of recording it.
    """
    if order.payment_status not in (PaymentStatus.PENDING, PaymentStatus.FAILED):
        raise POSOrderError(
            "This sale already has money against it. Void it and start again rather "
            "than changing the price under a settled payment."
        )
    if order.tenders.exists():
        raise POSOrderError("This sale already has tenders recorded.")
    if reason not in DISCOUNT_REASONS:
        raise POSOrderError(f"Reason must be one of: {', '.join(DISCOUNT_REASONS)}.")

    base = (order.subtotal or ZERO) - (order.discount_amount or ZERO)
    if base <= ZERO:
        raise POSOrderError("Nothing left to discount on this sale.")

    if percent is not None:
        pct = Decimal(str(percent))
        off = (base * pct / Decimal("100")).quantize(Decimal("0.01"))
    elif amount is not None:
        off = Decimal(str(amount)).quantize(Decimal("0.01"))
        pct = (off / base * Decimal("100")).quantize(Decimal("0.01"))
    else:
        raise POSOrderError("Give either a percent or an amount.")

    if off <= ZERO:
        raise POSOrderError("A discount must be positive.")
    if off > base:
        raise POSOrderError("A discount cannot exceed the value of the sale.")

    ceiling = discount_ceiling_pct()
    if pct > ceiling and approved_by is None:
        raise POSOrderError(
            f"{pct}% is over the {ceiling}% staff ceiling. A manager must approve it."
        )

    previous = order.manual_discount_amount or ZERO
    order.manual_discount_amount = off
    order.manual_discount_reason = reason
    order.manual_discount_approved_by = approved_by
    order.grand_total = (order.grand_total + previous - off).quantize(Decimal("0.01"))
    order.save(update_fields=[
        "manual_discount_amount", "manual_discount_reason",
        "manual_discount_approved_by", "grand_total",
    ])

    logger.info(
        "pos_manual_discount_applied",
        order_id=str(order.id), amount=str(off), percent=str(pct), reason=reason,
        staff=getattr(staff, "id", None), approved_by=getattr(approved_by, "id", None),
        over_ceiling=pct > ceiling,
    )
    return order


def authenticate_approver(*, email: str, password: str):
    """
    Verify a manager standing at the counter.

    Reuses the real login check rather than inventing a PIN store: a PIN is
    another credential to leak, and a manager already has an account. Staff
    accounts cannot approve their own overrides — only admins.
    """
    from django.contrib.auth import authenticate

    from apps.accounts.models import UserRole

    user = authenticate(username=email, password=password)
    if user is None or not user.is_active:
        return None
    if user.role != UserRole.ADMIN:
        return None
    return user
