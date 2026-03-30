"""
surcharge.services
~~~~~~~~~~~~~~~~~~

Calculation engine.  All functions are pure (no DB writes).

Public API:
    calculate_surcharges(context) → SurchargeResult
    calculate_tax(...)            → list[SurchargeLineItem]
    calculate_shipping(...)       → list[SurchargeLineItem]
    calculate_fees(...)           → list[SurchargeLineItem]

SurchargeContext  – input bundle passed to the engine
SurchargeResult   – structured output with full breakdown
SurchargeLineItem – one applied rule (name, amount, type, rule_id)

Integration:
    Cart → POST /cart/surcharges/
        engine.calculate_surcharges(SurchargeContext.from_cart(cart, address, method))

    Order placement → place_order() calls the engine to populate
        order.tax_amount, order.shipping_cost, and any fee rows.

Rule evaluation:
    1. Load all active, not-expired rules ordered by priority
    2. For each rule, evaluate_conditions(rule, context) → bool
    3. If matches → compute amount → append SurchargeLineItem
    4. Shipping: first non-additive match wins; additive rules always stack
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from django.utils import timezone
from apps.features import services as feature_services

from core.logging import get_logger
from .models import TaxRule, ShippingRule, FeeRule, ShippingMethod, AmountType

logger = get_logger(__name__)

ZERO = Decimal("0.00")
TWO_DP = Decimal("0.01")


# ─────────────────────────────────────────────────────────────
#  Data transfer objects
# ─────────────────────────────────────────────────────────────

@dataclass
class CartItemContext:
    """Lightweight representation of a cart/order item for engine input."""
    variant_id:   str
    category_id:  str
    quantity:     int
    unit_price:   Decimal
    weight_grams: int = 0


@dataclass
class SurchargeContext:
    """
    All inputs the engine needs to evaluate and apply rules.

    Build via:
        SurchargeContext.from_cart(cart, address, payment_method)
        SurchargeContext.from_order(order)
    """
    subtotal:       Decimal
    items:          list[CartItemContext] = field(default_factory=list)
    payment_method: str = ""
    state_code:     str = ""          # e.g. "MH", "DL"
    pincode:        str = ""
    user_role:      str = "customer"
    currency:       str = "INR"

    @property
    def total_weight_grams(self) -> int:
        return sum(i.weight_grams * i.quantity for i in self.items)

    @property
    def total_weight_kg(self) -> Decimal:
        return Decimal(self.total_weight_grams) / 1000

    @property
    def category_ids(self) -> set[str]:
        return {i.category_id for i in self.items}

    # ── Factory methods ───────────────────────────────────────

    @classmethod
    def from_cart(cls, cart, address: dict, payment_method: str = "") -> "SurchargeContext":
        from apps.cart.selectors import calculate_cart_totals
        totals = calculate_cart_totals(cart)
        items  = [
            CartItemContext(
                variant_id=i["variant_id"],
                category_id="",    # enriched below if needed
                quantity=i["quantity"],
                unit_price=Decimal(str(i["unit_price"])),
                weight_grams=0,
            )
            for i in totals["items"]
        ]
        return cls(
            subtotal=Decimal(str(totals["subtotal"])),
            items=items,
            payment_method=payment_method,
            state_code=str(address.get("state_code") or address.get("state") or "").strip(),
            pincode=str(address.get("pincode") or "").strip(),
        )

    @classmethod
    def from_order(cls, order) -> "SurchargeContext":
        items = [
            CartItemContext(
                variant_id=str(i.variant_id) if i.variant_id else "",
                category_id=i.product_snapshot.get("category_id", ""),
                quantity=i.quantity,
                unit_price=i.unit_price,
                weight_grams=i.product_snapshot.get("weight_grams", 0),
            )
            for i in order.items.all()
        ]
        address = order.shipping_address or {}
        return cls(
            subtotal=order.subtotal,
            items=items,
            payment_method=order.payment_method,
            state_code=str(address.get("state_code") or address.get("state") or "").strip(),
            pincode=str(address.get("pincode") or "").strip(),
            currency=order.currency,
        )


@dataclass
class SurchargeLineItem:
    """One applied rule — part of the result breakdown."""
    name:       str
    rule_type:  str                   # "tax" | "shipping" | "fee"
    rule_id:    str
    amount:     Decimal
    rate:       Decimal | None = None  # % rate if applicable
    is_negative: bool = False          # True = discount
    metadata:   dict  = field(default_factory=dict)


@dataclass
class SurchargeResult:
    """
    Full result of the surcharge calculation engine.

    tax_total      – sum of all tax line items
    shipping_total – sum of all shipping line items
    fee_total      – sum of all fee line items (positive only)
    discount_total – sum of all negative fee line items
    grand_total    – subtotal + tax + shipping + fee - discount
    """
    subtotal:       Decimal
    tax_total:      Decimal
    shipping_total: Decimal
    fee_total:      Decimal
    discount_total: Decimal
    grand_total:    Decimal
    breakdown:      list[SurchargeLineItem]

    def as_dict(self) -> dict:
        return {
            "subtotal":       str(self.subtotal),
            "tax_total":      str(self.tax_total),
            "shipping_total": str(self.shipping_total),
            "fee_total":      str(self.fee_total),
            "discount_total": str(self.discount_total),
            "grand_total":    str(self.grand_total),
            "breakdown": [
                {
                    "name":       li.name,
                    "rule_type":  li.rule_type,
                    "rule_id":    li.rule_id,
                    "amount":     str(li.amount),
                    "rate":       str(li.rate) if li.rate else None,
                    "is_negative": li.is_negative,
                    "metadata":   li.metadata,
                }
                for li in self.breakdown
            ],
        }


# ─────────────────────────────────────────────────────────────
#  Main engine
# ─────────────────────────────────────────────────────────────

def calculate_surcharges(ctx: SurchargeContext) -> SurchargeResult:
    """
    Run the full surcharge calculation engine against a context.

    Execution order:
      1. Tax rules   (all matching rules applied)
      2. Shipping    (first non-additive match wins; additive stack)
      3. Fee rules   (all matching rules applied)

    Returns a SurchargeResult with full line-item breakdown.
    """
    tax_lines      = _apply_tax_rules(ctx)
    shipping_lines = _apply_shipping_rules(ctx)
    fee_lines      = _apply_fee_rules(ctx)

    all_lines = tax_lines + shipping_lines + fee_lines

    tax_total      = _sum(l.amount for l in tax_lines if not l.is_negative)
    shipping_total = _sum(l.amount for l in shipping_lines)
    fee_total      = _sum(l.amount for l in fee_lines if not l.is_negative)
    discount_total = _sum(l.amount for l in fee_lines if l.is_negative)

    grand_total = _round(
        ctx.subtotal + tax_total + shipping_total + fee_total - discount_total
    )

    result = SurchargeResult(
        subtotal=ctx.subtotal,
        tax_total=_round(tax_total),
        shipping_total=_round(shipping_total),
        fee_total=_round(fee_total),
        discount_total=_round(discount_total),
        grand_total=grand_total,
        breakdown=all_lines,
    )

    logger.info(
        "surcharges_calculated",
        subtotal=str(ctx.subtotal),
        tax=str(result.tax_total),
        shipping=str(result.shipping_total),
        fees=str(result.fee_total),
        discounts=str(result.discount_total),
        grand_total=str(result.grand_total),
        rules_applied=len(all_lines),
    )
    return result


# ─────────────────────────────────────────────────────────────
#  Tax engine
# ─────────────────────────────────────────────────────────────

def _apply_tax_rules(ctx: SurchargeContext) -> list[SurchargeLineItem]:
    now   = timezone.now()
    rules = (
        TaxRule.objects
        .filter(is_active=True)
        .filter(
            models.Q(start_date__isnull=True) | models.Q(start_date__lte=now)
        )
        .filter(
            models.Q(end_date__isnull=True) | models.Q(end_date__gte=now)
        )
        .prefetch_related("categories")
        .order_by("priority")
    )

    lines = []
    for rule in rules:
        if not _evaluate_conditions(rule.conditions, ctx):
            continue
        if not _tax_applies_to_items(rule, ctx):
            continue

        taxable = ctx.subtotal   # TODO: for inclusive tax, extract from unit price
        amount  = _round(taxable * rule.rate / 100)

        lines.append(SurchargeLineItem(
            name=rule.name,
            rule_type="tax",
            rule_id=str(rule.id),
            amount=amount,
            rate=rule.rate,
            is_negative=False,
            metadata={
                "tax_type":     rule.tax_type,
                "hsn_code":     rule.hsn_code,
                "is_inclusive": rule.is_inclusive,
            },
        ))
    return lines


def _tax_applies_to_items(rule: TaxRule, ctx: SurchargeContext) -> bool:
    """Check if the tax rule targets the right categories."""
    from .models import TaxAppliesTo
    if rule.applies_to == TaxAppliesTo.ALL:
        return True
    if rule.applies_to == TaxAppliesTo.CATEGORY:
        rule_category_ids = {str(c.id) for c in rule.categories.all()}
        return bool(rule_category_ids & ctx.category_ids)
    return True


# ─────────────────────────────────────────────────────────────
#  Shipping engine
# ─────────────────────────────────────────────────────────────

def _apply_shipping_rules(ctx: SurchargeContext) -> list[SurchargeLineItem]:
    now   = timezone.now()
    rules = (
        ShippingRule.objects
        .filter(is_active=True)
        .filter(
            models.Q(start_date__isnull=True) | models.Q(start_date__lte=now)
        )
        .filter(
            models.Q(end_date__isnull=True) | models.Q(end_date__gte=now)
        )
        .order_by("priority")
    )

    lines          = []
    base_found     = False    # tracks if a non-additive rule has matched

    for rule in rules:
        if not _evaluate_conditions(rule.conditions, ctx):
            continue

        # Non-additive rule: only apply if no non-additive rule matched yet
        if not rule.is_additive:
            if base_found:
                continue
            base_found = True

        amount = _compute_shipping_amount(rule, ctx)
        if amount is None:
            continue

        lines.append(SurchargeLineItem(
            name=rule.name,
            rule_type="shipping",
            rule_id=str(rule.id),
            amount=amount,
            metadata={
                "method":          rule.method,
                "carrier":         rule.carrier,
                "estimated_days":  f"{rule.estimated_days_min}–{rule.estimated_days_max}",
                "is_additive":     rule.is_additive,
            },
        ))
    if lines:
        return lines
    return _fallback_shipping_from_standard_setting(ctx)


def _fallback_shipping_from_standard_setting(ctx: SurchargeContext) -> list[SurchargeLineItem]:
    """
    Backward-compatible fallback:
    use AppSetting `shipping.standard` when no ShippingRule matched/existed.
    """
    config = feature_services.get_setting("shipping.standard", default={}) or {}
    if not isinstance(config, dict):
        return []

    flat_rate = _to_decimal(config.get("flat_rate"), default=ZERO)
    threshold = _to_decimal(config.get("free_shipping_threshold"), default=ZERO)

    if flat_rate <= ZERO and threshold <= ZERO:
        return []

    amount = ZERO if (threshold > ZERO and ctx.subtotal >= threshold) else flat_rate
    amount = _round(amount)
    return [
        SurchargeLineItem(
            name="Standard Shipping",
            rule_type="shipping",
            rule_id="setting:shipping.standard",
            amount=amount,
            metadata={
                "source": "app_setting",
                "flat_rate": str(flat_rate),
                "free_shipping_threshold": str(threshold),
            },
        )
    ]


def _compute_shipping_amount(rule: ShippingRule, ctx: SurchargeContext) -> Decimal | None:
    method = rule.method

    if method == ShippingMethod.FREE:
        return ZERO

    if method == ShippingMethod.FREE_THRESHOLD:
        amount = ZERO if ctx.subtotal >= rule.free_threshold_amount else rule.flat_rate

    elif method == ShippingMethod.FLAT:
        amount = rule.flat_rate

    elif method == ShippingMethod.PERCENTAGE:
        amount = _round(ctx.subtotal * rule.percentage_rate / 100)

    elif method == ShippingMethod.WEIGHT_BASED:
        amount = _round(ctx.total_weight_kg * rule.per_kg_rate + rule.flat_rate)

    else:
        return None

    # Apply max_charge cap
    if rule.max_charge is not None:
        amount = min(amount, rule.max_charge)

    return _round(amount)


# ─────────────────────────────────────────────────────────────
#  Fee engine
# ─────────────────────────────────────────────────────────────

def _apply_fee_rules(ctx: SurchargeContext) -> list[SurchargeLineItem]:
    now   = timezone.now()
    rules = (
        FeeRule.objects
        .filter(is_active=True)
        .filter(
            models.Q(start_date__isnull=True) | models.Q(start_date__lte=now)
        )
        .filter(
            models.Q(end_date__isnull=True) | models.Q(end_date__gte=now)
        )
        .order_by("priority")
    )

    lines = []
    for rule in rules:
        if not _evaluate_conditions(rule.conditions, ctx):
            continue

        amount = _compute_fee_amount(rule, ctx)
        lines.append(SurchargeLineItem(
            name=rule.name,
            rule_type="fee",
            rule_id=str(rule.id),
            amount=amount,
            rate=rule.amount if rule.amount_type == AmountType.PERCENTAGE else None,
            is_negative=rule.is_negative,
            metadata={"fee_type": rule.fee_type},
        ))
    return lines


def _compute_fee_amount(rule: FeeRule, ctx: SurchargeContext) -> Decimal:
    if rule.amount_type == AmountType.FLAT:
        amount = rule.amount
    else:
        amount = _round(ctx.subtotal * rule.amount / 100)

    if rule.max_amount is not None:
        amount = min(amount, rule.max_amount)

    return _round(amount)


# ─────────────────────────────────────────────────────────────
#  Condition evaluator
# ─────────────────────────────────────────────────────────────

def _evaluate_conditions(conditions: dict, ctx: SurchargeContext) -> bool:
    """
    Return True if ALL non-empty conditions in the dict are satisfied.
    Unknown/future condition keys are silently ignored (forward-compatible).
    """
    if not conditions:
        return True

    # ── Order value range ─────────────────────────────────────
    min_val = conditions.get("min_order_value")
    if min_val is not None and ctx.subtotal < Decimal(str(min_val)):
        return False

    max_val = conditions.get("max_order_value")
    if max_val is not None and ctx.subtotal > Decimal(str(max_val)):
        return False

    # ── Region: state code ────────────────────────────────────
    states = conditions.get("states")
    if states and ctx.state_code and ctx.state_code not in states:
        return False

    # ── Region: pincode ───────────────────────────────────────
    pincodes = conditions.get("pincodes")
    if pincodes and ctx.pincode and ctx.pincode not in pincodes:
        return False

    # ── Payment method ────────────────────────────────────────
    payment_methods = conditions.get("payment_methods")
    if payment_methods and ctx.payment_method not in payment_methods:
        return False

    # ── User role ─────────────────────────────────────────────
    user_roles = conditions.get("user_roles")
    if user_roles and ctx.user_role not in user_roles:
        return False

    # ── Category (any item must be in the list) ───────────────
    category_ids = conditions.get("category_ids")
    if category_ids and not (set(category_ids) & ctx.category_ids):
        return False

    # ── Weight range ──────────────────────────────────────────
    min_wt = conditions.get("min_weight_grams")
    if min_wt is not None and ctx.total_weight_grams < min_wt:
        return False

    max_wt = conditions.get("max_weight_grams")
    if max_wt is not None and ctx.total_weight_grams > max_wt:
        return False

    return True


# ─────────────────────────────────────────────────────────────
#  Cart + Order integration helpers
# ─────────────────────────────────────────────────────────────

def get_surcharges_for_cart(cart, address: dict, payment_method: str = "") -> SurchargeResult:
    """
    Convenience wrapper for the cart flow.
    Called from the /cart/surcharges/ endpoint and from place_order().
    """
    ctx = SurchargeContext.from_cart(cart, address, payment_method)
    return calculate_surcharges(ctx)


def get_surcharges_for_order(order) -> SurchargeResult:
    """
    Convenience wrapper for the order flow.
    Used to recompute surcharges for an existing order (e.g. admin reconciliation).
    """
    ctx = SurchargeContext.from_order(order)
    return calculate_surcharges(ctx)


def apply_surcharges_to_order(order, address: dict) -> SurchargeResult:
    """
    Calculate surcharges and write the results back to the order fields.
    Called in place_order() before saving the order.

    Updates: order.tax_amount, order.shipping_cost, order.grand_total
    Returns the full SurchargeResult for use in the response.
    """
    ctx    = SurchargeContext.from_order(order)
    result = calculate_surcharges(ctx)

    order.tax_amount    = result.tax_total
    order.shipping_cost = result.shipping_total
    order.grand_total   = result.grand_total
    # Fee totals are already baked into grand_total via the engine
    return result


# ─────────────────────────────────────────────────────────────
#  Utilities
# ─────────────────────────────────────────────────────────────

def _round(value: Decimal) -> Decimal:
    return value.quantize(TWO_DP, rounding=ROUND_HALF_UP)


def _sum(iterable) -> Decimal:
    return sum(iterable, ZERO)


def _to_decimal(value, default: Decimal = ZERO) -> Decimal:
    try:
        if value is None or value == "":
            return default
        return Decimal(str(value))
    except Exception:
        return default


# Needed for Q objects in the functions above
from django.db import models
