"""
accounts.selectors
~~~~~~~~~~~~~~~~~~
Read-only query helpers.  Views and services import from here
instead of writing ORM queries inline.

Design rule: selectors NEVER mutate state.
"""
from __future__ import annotations

from django.utils import timezone

from .models import User, Address, LoginAttempt


# ─────────────────────────────────────────────────────────────
#  User selectors
# ─────────────────────────────────────────────────────────────

def get_user_by_id(user_id) -> User | None:
    try:
        # Don't restrict to is_active=True for admin view
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        return None

def get_all_users():
    return User.objects.all().order_by("-date_joined")


def get_user_by_email(email: str) -> User | None:
    try:
        return User.objects.get(email__iexact=email.strip())
    except User.DoesNotExist:
        return None


def get_user_by_reset_token(token: str) -> User | None:
    """Return a user whose reset token is valid and not expired."""
    try:
        return User.objects.get(
            password_reset_token=token,
            password_reset_expires__gt=timezone.now(),
            is_active=True,
        )
    except User.DoesNotExist:
        return None


def email_exists(email: str) -> bool:
    return User.objects.filter(email__iexact=email.strip()).exists()


# ─────────────────────────────────────────────────────────────
#  Address selectors
# ─────────────────────────────────────────────────────────────

def get_addresses_for_user(user: User):
    return Address.objects.filter(user=user).order_by("-is_default", "-created_at")


def get_address_by_id(address_id, user: User) -> Address | None:
    try:
        return Address.objects.get(id=address_id, user=user)
    except Address.DoesNotExist:
        return None


# ─────────────────────────────────────────────────────────────
#  Login Attempt selectors
# ─────────────────────────────────────────────────────────────

def get_recent_failed_attempts(email: str, minutes: int = 30) -> int:
    """Count failed login attempts for an email in the last N minutes."""
    since = timezone.now() - timezone.timedelta(minutes=minutes)
    return LoginAttempt.objects.filter(
        email__iexact=email,
        successful=False,
        attempted_at__gte=since,
    ).count()
