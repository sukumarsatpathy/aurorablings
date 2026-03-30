"""
cart.models
~~~~~~~~~~~

Cart identity strategy:
  ┌──────────────────────────────────────────────────────────┐
  │  Authenticated user   → Cart.user FK (non-null)          │
  │  Anonymous visitor    → Cart.session_key (UUID in header) │
  └──────────────────────────────────────────────────────────┘

When a guest logs in, CartService.merge_guest_cart() is called to
fold the guest cart into the user's active cart.

CartItem stores a unit_price SNAPSHOT at time of add so that:
  - Price changes after adding don't silently alter the cart total.
  - The snapshot is refreshed when the customer explicitly updates qty.
  - At checkout, the snapshot is validated against current live price.
"""

import uuid
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator


# ─────────────────────────────────────────────────────────────
#  Cart Status
# ─────────────────────────────────────────────────────────────

class CartStatus(models.TextChoices):
    ACTIVE    = "active",    _("Active")
    MERGED    = "merged",    _("Merged into user cart")
    ABANDONED = "abandoned", _("Abandoned")
    CONVERTED = "converted", _("Converted to Order")


# ─────────────────────────────────────────────────────────────
#  Cart
# ─────────────────────────────────────────────────────────────

class Cart(models.Model):
    """
    A shopping cart — belongs to either a user or a session (guest).

    Rules:
      - A user has at most one ACTIVE cart.
      - A session_key identifies a guest cart; it is a UUID4 string
        generated client-side (or by CartService.get_or_create_guest_cart).
      - Exactly one of (user, session_key) is set; never both.
    """

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # ── Identity: user OR guest (never both) ──────────────────
    user        = models.OneToOneField(
        "accounts.User",
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name="cart",
    )
    session_key = models.CharField(
        max_length=64, null=True, blank=True,
        db_index=True,
        help_text="UUID for anonymous guest carts. Set via X-Cart-Token header.",
    )

    status     = models.CharField(
        max_length=15, choices=CartStatus.choices, default=CartStatus.ACTIVE, db_index=True
    )
    expires_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Guest carts auto-expire after 30 days of inactivity.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = _("cart")
        verbose_name_plural = _("carts")
        ordering            = ["-created_at"]
        constraints         = [
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(status="active"),
                name="unique_active_cart_per_user",
            ),
            models.CheckConstraint(
                check=(
                    models.Q(user__isnull=False, session_key__isnull=True) |
                    models.Q(user__isnull=True, session_key__isnull=False)
                ),
                name="cart_owner_xor",          # user XOR session_key
            ),
        ]

    @property
    def is_expired(self) -> bool:
        return bool(self.expires_at and timezone.now() > self.expires_at)

    @property
    def is_guest(self) -> bool:
        return self.user_id is None

    @property
    def item_count(self) -> int:
        return self.items.aggregate(
            total=models.Sum("quantity")
        )["total"] or 0

    @property
    def subtotal(self):
        from django.db.models import F, Sum, DecimalField, ExpressionWrapper
        result = self.items.aggregate(
            total=Sum(
                ExpressionWrapper(
                    F("unit_price") * F("quantity"),
                    output_field=DecimalField(max_digits=14, decimal_places=2),
                )
            )
        )
        return result["total"] or 0

    def touch(self):
        """Bump updated_at + extend guest expiry."""
        self.updated_at = timezone.now()
        if self.is_guest:
            from datetime import timedelta
            self.expires_at = timezone.now() + timedelta(days=30)
        self.save(update_fields=["updated_at", "expires_at"])

    def __str__(self):
        owner = self.user.email if self.user else f"guest:{self.session_key[:8]}"
        return f"Cart({owner}) — {self.status}"


# ─────────────────────────────────────────────────────────────
#  Cart Item
# ─────────────────────────────────────────────────────────────

class CartItem(models.Model):
    """
    A single line in the cart.

    unit_price is a SNAPSHOT of the variant's price at time of add.
    It is refreshed when the user explicitly changes the quantity.
    """

    id       = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cart     = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    variant  = models.ForeignKey(
        "catalog.ProductVariant",
        on_delete=models.CASCADE,
        related_name="cart_items",
    )

    quantity   = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
    )
    unit_price = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text="Price snapshot at time of add — not live.",
    )

    # Preserve compare_at_price snapshot so the cart can show strikethrough
    compare_at_price = models.DecimalField(
        max_digits=12, decimal_places=2,
        null=True, blank=True,
        help_text="Snapshot of compare_at_price at time of add.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = _("cart item")
        verbose_name_plural = _("cart items")
        unique_together     = [("cart", "variant")]    # one row per variant per cart
        ordering            = ["created_at"]

    @property
    def line_total(self):
        return self.unit_price * self.quantity

    @property
    def is_price_stale(self) -> bool:
        """True if the current variant price differs from the snapshot."""
        return self.variant.effective_price != self.unit_price

    def __str__(self):
        return f"{self.variant.sku} × {self.quantity} @ {self.unit_price}"
