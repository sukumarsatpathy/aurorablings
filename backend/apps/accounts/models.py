import uuid
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .managers import CustomUserManager


# ─────────────────────────────────────────────────────────────
#  Role Choices
# ─────────────────────────────────────────────────────────────

class UserRole(models.TextChoices):
    ADMIN    = "admin",    _("Admin")
    STAFF    = "staff",    _("Staff")
    CUSTOMER = "customer", _("Customer")


# ─────────────────────────────────────────────────────────────
#  Custom User Model
# ─────────────────────────────────────────────────────────────

class User(AbstractBaseUser, PermissionsMixin):
    """
    Aurora Blings custom user model.

    - No username field; email is the unique login identifier.
    - Role-based access: admin / staff / customer.
    - Tracks failed login attempts for brute-force protection.
    - Soft-deletable via `is_active = False`.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # ── Identity ───────────────────────────────────────────────
    email      = models.EmailField(_("email address"), unique=True, db_index=True)
    first_name = models.CharField(_("first name"), max_length=150, blank=True)
    last_name  = models.CharField(_("last name"),  max_length=150, blank=True)
    phone      = models.CharField(_("phone number"), max_length=20, blank=True)

    # ── Role ───────────────────────────────────────────────────
    role = models.CharField(
        _("role"),
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.CUSTOMER,
        db_index=True,
    )

    # ── Flags ──────────────────────────────────────────────────
    is_active       = models.BooleanField(_("active"), default=True)
    is_staff        = models.BooleanField(_("staff status"), default=False)
    is_email_verified = models.BooleanField(_("email verified"), default=False)

    # ── Security / Brute-force tracking ────────────────────────
    failed_login_attempts = models.PositiveSmallIntegerField(default=0)
    last_failed_login     = models.DateTimeField(null=True, blank=True)
    locked_until          = models.DateTimeField(null=True, blank=True)

    # ── Password reset flow ────────────────────────────────────
    password_reset_token    = models.CharField(max_length=64, blank=True)
    password_reset_expires  = models.DateTimeField(null=True, blank=True)

    # ── Timestamps ─────────────────────────────────────────────
    date_joined = models.DateTimeField(_("date joined"), default=timezone.now)
    updated_at  = models.DateTimeField(auto_now=True)

    objects = CustomUserManager()

    USERNAME_FIELD  = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class Meta:
        verbose_name        = _("user")
        verbose_name_plural = _("users")
        ordering            = ["-date_joined"]

    # ── Properties ─────────────────────────────────────────────

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def get_full_name(self) -> str:
        """
        Django-compatible full-name accessor.
        Several services/serializers call this method.
        """
        return self.full_name

    def get_short_name(self) -> str:
        return self.first_name or self.email

    @property
    def is_locked(self) -> bool:
        if self.locked_until and timezone.now() < self.locked_until:
            return True
        return False

    def __str__(self):
        return f"{self.email} ({self.role})"


# ─────────────────────────────────────────────────────────────
#  Address Model
# ─────────────────────────────────────────────────────────────

class AddressType(models.TextChoices):
    SHIPPING = "shipping", _("Shipping")
    BILLING  = "billing",  _("Billing")


class Address(models.Model):
    """
    Shipping or billing address linked to a user.
    A user can have many addresses; one can be marked default per type.
    """

    id   = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="addresses",
    )

    # ── Type ───────────────────────────────────────────────────
    address_type = models.CharField(
        max_length=10,
        choices=AddressType.choices,
        default=AddressType.SHIPPING,
    )
    is_default = models.BooleanField(default=False)

    # ── Fields ─────────────────────────────────────────────────
    full_name    = models.CharField(max_length=255)
    line1        = models.CharField(_("address line 1"), max_length=255)
    line2        = models.CharField(_("address line 2"), max_length=255, blank=True)
    city         = models.CharField(max_length=100)
    state        = models.CharField(max_length=100, blank=True)
    postal_code  = models.CharField(max_length=20)
    country      = models.CharField(max_length=100, default="India")
    phone        = models.CharField(max_length=20, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = _("address")
        verbose_name_plural = _("addresses")
        ordering            = ["-is_default", "-created_at"]

    def __str__(self):
        return f"{self.full_name}, {self.line1}, {self.city}"


# ─────────────────────────────────────────────────────────────
#  Login Attempt Log
# ─────────────────────────────────────────────────────────────

class LoginAttempt(models.Model):
    """
    Immutable audit log of every login attempt (success + failure).
    Used for security monitoring and account lockout logic.
    """

    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email      = models.EmailField(db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    successful = models.BooleanField(default=False)
    failure_reason = models.CharField(max_length=100, blank=True)
    attempted_at   = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name        = _("login attempt")
        verbose_name_plural = _("login attempts")
        ordering            = ["-attempted_at"]

    def __str__(self):
        status = "✓" if self.successful else "✗"
        return f"[{status}] {self.email} @ {self.attempted_at:%Y-%m-%d %H:%M}"
