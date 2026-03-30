"""
surcharge.models
~~~~~~~~~~~~~~~~

Three independent rule tables — each can be active, time-bounded,
and has a JSON `conditions` field for flexible criteria matching.

  TaxRule       – GST / VAT / custom tax (flat % or inclusive)
  ShippingRule  – flat / percentage / weight-based / free-threshold
  FeeRule       – COD fee / gateway fee / handling charge / platform fee

All rules share:
  is_active    – on/off switch
  priority     – lower = applied first; rules are evaluated in priority order
  start_date   – rule becomes active from this date (null = always)
  end_date     – rule expires after this date  (null = never)
  conditions   – JSON dict for flexible criteria (see condition schema below)

Condition schema (conditions JSON field):
  {
    "min_order_value":  100.00,     # apply only if subtotal >= this
    "max_order_value":  5000.00,    # apply only if subtotal <= this
    "states":           ["MH","DL"], # ISO state codes (shipping address)
    "pincodes":         ["400001"],  # exact pincode match
    "category_ids":     ["uuid1"],   # any item in these categories
    "payment_methods":  ["cod"],     # specific payment methods
    "user_roles":       ["customer"],
    "min_weight_grams": 500,
    "max_weight_grams": 2000,
  }
  All keys are optional — missing keys mean "no restriction".
"""

import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator


# ─────────────────────────────────────────────────────────────
#  Shared base
# ─────────────────────────────────────────────────────────────

class BaseRule(models.Model):
    """Abstract mixin shared by all rule models."""

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name        = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_active   = models.BooleanField(default=True, db_index=True)
    priority    = models.PositiveSmallIntegerField(
        default=10,
        help_text="Lower number = evaluated first. Rules with equal priority are all applied.",
    )
    start_date  = models.DateTimeField(null=True, blank=True)
    end_date    = models.DateTimeField(null=True, blank=True)

    # Flexible condition bag — see module docstring for schema
    conditions  = models.JSONField(
        default=dict, blank=True,
        help_text="JSON conditions that must all match for this rule to apply.",
    )

    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        abstract  = True
        ordering  = ["priority", "name"]

    def __str__(self):
        return f"{self.name} [{'active' if self.is_active else 'inactive'}]"


# ─────────────────────────────────────────────────────────────
#  1.  Tax Rule
# ─────────────────────────────────────────────────────────────

class TaxType(models.TextChoices):
    GST      = "gst",      _("GST (India)")
    VAT      = "vat",      _("VAT")
    IGST     = "igst",     _("IGST (Inter-state India)")
    CUSTOM   = "custom",   _("Custom Tax")


class TaxAppliesTo(models.TextChoices):
    ALL        = "all",        _("All Products")
    CATEGORY   = "category",   _("Specific Categories")
    PRODUCT_TYPE = "product_type", _("Product Type")


class TaxRule(BaseRule):
    """
    A percentage-based tax rule.

    is_inclusive=True  → price already includes tax (display only, no addition)
    is_inclusive=False → tax is added on top of the subtotal

    hsn_code: Harmonised System of Nomenclature code for GST filing.
    """

    tax_type     = models.CharField(max_length=20, choices=TaxType.choices, default=TaxType.GST)
    tax_code     = models.CharField(max_length=50, blank=True, help_text="e.g. GST-18, VAT-5")
    hsn_code     = models.CharField(max_length=20, blank=True)
    rate         = models.DecimalField(
        max_digits=6, decimal_places=3,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Tax rate as a percentage (e.g. 18.000 for 18% GST).",
    )
    is_inclusive = models.BooleanField(
        default=False,
        help_text="If true, tax is already included in the product price.",
    )
    applies_to   = models.CharField(
        max_length=20, choices=TaxAppliesTo.choices, default=TaxAppliesTo.ALL
    )
    # Which categories this tax rule targets (used when applies_to=CATEGORY)
    categories   = models.ManyToManyField(
        "catalog.Category", blank=True, related_name="tax_rules"
    )

    class Meta(BaseRule.Meta):
        verbose_name        = _("tax rule")
        verbose_name_plural = _("tax rules")

    def __str__(self):
        return f"{self.name} — {self.rate}% {self.tax_type.upper()}"


# ─────────────────────────────────────────────────────────────
#  2.  Shipping Rule
# ─────────────────────────────────────────────────────────────

class ShippingMethod(models.TextChoices):
    FLAT           = "flat",            _("Flat Rate")
    PERCENTAGE     = "percentage",      _("Percentage of Order Value")
    WEIGHT_BASED   = "weight_based",    _("Weight Based (per kg)")
    FREE_THRESHOLD = "free_threshold",  _("Free Above Threshold")
    FREE           = "free",            _("Always Free")


class ShippingRule(BaseRule):
    """
    Determines the shipping cost for an order.

    Method resolution:
      FREE           → 0
      FREE_THRESHOLD → 0 if subtotal >= free_threshold_amount else flat_rate
      FLAT           → flat_rate
      PERCENTAGE     → subtotal * percentage_rate / 100
      WEIGHT_BASED   → total_weight_kg * per_kg_rate (+ optional flat_rate base)

    The FIRST matching rule (by priority) wins — subsequent rules are ignored
    unless `is_additive=True`.
    """

    method             = models.CharField(max_length=20, choices=ShippingMethod.choices, default=ShippingMethod.FLAT)
    carrier            = models.CharField(max_length=100, blank=True, help_text="e.g. FedEx, Delhivery, India Post")
    estimated_days_min = models.PositiveSmallIntegerField(default=3)
    estimated_days_max = models.PositiveSmallIntegerField(default=7)
    is_additive        = models.BooleanField(
        default=False,
        help_text="If true, this rule stacks on top of other matched shipping rules.",
    )

    # Rate fields (only relevant fields used depending on method)
    flat_rate              = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    percentage_rate        = models.DecimalField(
        max_digits=6, decimal_places=3, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    per_kg_rate            = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    free_threshold_amount  = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text="Order must be ≥ this value for FREE_THRESHOLD to kick in.",
    )
    max_charge             = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Cap the shipping charge at this amount.",
    )

    class Meta(BaseRule.Meta):
        verbose_name        = _("shipping rule")
        verbose_name_plural = _("shipping rules")

    def __str__(self):
        return f"{self.name} — {self.method} | {self.carrier}"


# ─────────────────────────────────────────────────────────────
#  3.  Fee Rule
# ─────────────────────────────────────────────────────────────

class FeeType(models.TextChoices):
    COD              = "cod",              _("Cash on Delivery Fee")
    PAYMENT_GATEWAY  = "payment_gateway",  _("Payment Gateway Fee")
    HANDLING         = "handling",         _("Handling / Packing Fee")
    PLATFORM         = "platform",         _("Platform Fee")
    SURCHARGE        = "surcharge",        _("General Surcharge")
    DISCOUNT         = "discount",         _("Discount / Waiver")


class AmountType(models.TextChoices):
    FLAT       = "flat",       _("Flat Amount")
    PERCENTAGE = "percentage", _("Percentage of Subtotal")


class FeeRule(BaseRule):
    """
    Additional fees or discounts applied to the cart/order.

    fee_type=DISCOUNT & amount_type=PERCENTAGE → negative surcharge
    (i.e. a waiver)
    """

    fee_type    = models.CharField(max_length=25, choices=FeeType.choices)
    amount_type = models.CharField(max_length=15, choices=AmountType.choices, default=AmountType.FLAT)
    amount      = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Flat amount OR percentage rate (e.g. 2.5 for 2.5%).",
    )
    is_negative = models.BooleanField(
        default=False,
        help_text="If true, this rule subtracts from the total (a discount/waiver).",
    )
    max_amount  = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Cap the calculated fee at this amount.",
    )

    class Meta(BaseRule.Meta):
        verbose_name        = _("fee rule")
        verbose_name_plural = _("fee rules")

    def __str__(self):
        sign  = "-" if self.is_negative else "+"
        value = f"{self.amount}%" if self.amount_type == AmountType.PERCENTAGE else f"₹{self.amount}"
        return f"{self.name} ({sign}{value})"
