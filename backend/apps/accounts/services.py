"""
accounts.services
~~~~~~~~~~~~~~~~~
All authentication business logic lives here.
Views call services; services call selectors and models.

Design rules:
  - Services MAY mutate state.
  - Services raise typed exceptions from core.exceptions.
  - Services emit structured log events for every auth action.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta

from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from core.exceptions import (
    ValidationError,
    NotFoundError,
    PermissionDeniedError,
    ConflictError,
)
from core.logging import get_logger
from audit.models import ActorType, AuditAction
from audit.services.activity_logger import log_activity
from .models import User, Address, LoginAttempt
from .selectors import get_user_by_email, email_exists, get_user_by_reset_token

logger = get_logger(__name__)

# ── Constants ─────────────────────────────────────────────────
MAX_FAILED_ATTEMPTS = 5        # lock after N consecutive failures
LOCK_DURATION_MINUTES = 30     # how long the lock lasts
RESET_TOKEN_EXPIRY_HOURS = 2   # password reset link lifetime


def _actor_type_for_user(user: User | None) -> str:
    if not user:
        return ActorType.SYSTEM
    if user.role == "admin":
        return ActorType.ADMIN
    if user.role == "staff":
        return ActorType.STAFF
    return ActorType.CUSTOMER


# ─────────────────────────────────────────────────────────────
#  Registration
# ─────────────────────────────────────────────────────────────

def register_user(
    *,
    email: str,
    password: str,
    first_name: str,
    last_name: str,
    phone: str = "",
    role: str = "customer",
) -> User:
    """
    Create a new user account.

    Raises:
        ConflictError: if email is already registered.
        ValidationError: if password is too weak.
    """
    email = email.strip().lower()

    if email_exists(email):
        raise ConflictError("An account with this email address already exists.")

    _validate_password_strength(password)

    user = User.objects.create_user(
        email=email,
        password=password,
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        phone=phone.strip(),
        role=role,
    )

    logger.info(
        "user_registered",
        user_id=str(user.id),
        email=user.email,
        role=user.role,
    )
    return user


# ─────────────────────────────────────────────────────────────
#  Login / Token issuance
# ─────────────────────────────────────────────────────────────

def login_user(
    *,
    email: str,
    password: str,
    ip_address: str | None = None,
    user_agent: str = "",
    request=None,
) -> dict:
    """
    Authenticate a user and return JWT access + refresh tokens.

    Raises:
        PermissionDeniedError: account is locked.
        ValidationError: bad credentials.

    Returns:
        {"access": "...", "refresh": "...", "user": User}
    """
    email = email.strip().lower()
    user = get_user_by_email(email)

    def _log_attempt(successful: bool, reason: str = ""):
        LoginAttempt.objects.create(
            email=email,
            ip_address=ip_address,
            user_agent=user_agent,
            successful=successful,
            failure_reason=reason,
        )

    # ── 1. Account exists? ────────────────────────────────────
    if not user:
        _log_attempt(False, "user_not_found")
        log_activity(
            user=None,
            actor_type=ActorType.SYSTEM,
            action=AuditAction.LOGIN,
            entity_type="auth",
            description="Login failed: user not found",
            metadata={"email": email, "reason": "user_not_found", "status": "failed"},
            request=request,
        )
        logger.warning("login_failed", email=email, reason="user_not_found", ip=ip_address)
        raise ValidationError("Invalid email or password.")     # intentionally vague

    # ── 2. Account locked? ────────────────────────────────────
    if user.is_locked:
        _log_attempt(False, "account_locked")
        log_activity(
            user=user,
            actor_type=_actor_type_for_user(user),
            action=AuditAction.LOGIN,
            entity_type="auth",
            entity_id=str(user.id),
            description="Login blocked: account locked",
            metadata={"email": email, "reason": "account_locked", "status": "failed"},
            request=request,
        )
        logger.warning("login_blocked", email=email, reason="locked", ip=ip_address)
        raise PermissionDeniedError(
            f"Account locked due to too many failed attempts. "
            f"Try again after {user.locked_until.strftime('%H:%M UTC')}."
        )

    # ── 3. Password correct? ──────────────────────────────────
    if not user.check_password(password):
        _record_failed_attempt(user)
        _log_attempt(False, "wrong_password")
        log_activity(
            user=user,
            actor_type=_actor_type_for_user(user),
            action=AuditAction.LOGIN,
            entity_type="auth",
            entity_id=str(user.id),
            description="Login failed: wrong password",
            metadata={"email": email, "reason": "wrong_password", "status": "failed"},
            request=request,
        )
        logger.warning("login_failed", email=email, reason="wrong_password", ip=ip_address)

        remaining = MAX_FAILED_ATTEMPTS - user.failed_login_attempts
        if remaining <= 0:
            raise PermissionDeniedError(
                f"Account locked for {LOCK_DURATION_MINUTES} minutes after too many failed attempts."
            )
        raise ValidationError(
            f"Invalid email or password. {remaining} attempt(s) remaining before lockout."
        )

    # ── 4. Account active? ────────────────────────────────────
    if not user.is_active:
        _log_attempt(False, "account_inactive")
        log_activity(
            user=user,
            actor_type=_actor_type_for_user(user),
            action=AuditAction.LOGIN,
            entity_type="auth",
            entity_id=str(user.id),
            description="Login blocked: account inactive",
            metadata={"email": email, "reason": "account_inactive", "status": "failed"},
            request=request,
        )
        raise PermissionDeniedError("This account has been deactivated.")

    # ── 5. Success — reset failure counters ───────────────────
    _reset_failed_attempts(user)
    _log_attempt(True)
    log_activity(
        user=user,
        actor_type=_actor_type_for_user(user),
        action=AuditAction.LOGIN,
        entity_type="auth",
        entity_id=str(user.id),
        description=f"{user.role.title()} logged in",
        metadata={"email": email, "status": "success"},
        request=request,
    )

    tokens = _issue_tokens(user)
    logger.info("login_success", user_id=str(user.id), email=email, ip=ip_address)
    return {**tokens, "user": user}


def logout_user(refresh_token: str, request=None, user=None) -> None:
    """
    Blacklist the refresh token so it cannot be used to get new access tokens.
    Requires SIMPLE_JWT['ROTATE_REFRESH_TOKENS'] and token_blacklist app.
    """
    try:
        token = RefreshToken(refresh_token)
        token.blacklist()
        log_activity(
            user=user if user and getattr(user, "is_authenticated", False) else None,
            actor_type=_actor_type_for_user(user),
            action=AuditAction.LOGOUT,
            entity_type="auth",
            entity_id=str(user.id) if user and getattr(user, "is_authenticated", False) else None,
            description=f"{getattr(user, 'role', 'user').title()} logged out",
            request=request,
        )
        logger.info("logout", action="token_blacklisted")
    except Exception as exc:        # noqa: BLE001
        logger.warning("logout_failed", error=str(exc))
        raise ValidationError("Invalid or expired refresh token.")


# ─────────────────────────────────────────────────────────────
#  Password Reset
# ─────────────────────────────────────────────────────────────

def initiate_password_reset(*, email: str) -> str:
    """
    Generate a one-time reset token and (in production) queue an email.

    Always returns success to prevent user enumeration attacks.
    The token is returned here so it can be wired to the email task.
    """
    email = email.strip().lower()
    user = get_user_by_email(email)

    if not user:
        logger.info("password_reset_noop", email=email, reason="user_not_found")
        return ""               # silent — do not reveal if email exists

    token = secrets.token_urlsafe(32)
    token_hash = _hash_token(token)

    user.password_reset_token   = token_hash
    user.password_reset_expires = timezone.now() + timedelta(hours=RESET_TOKEN_EXPIRY_HOURS)
    user.save(update_fields=["password_reset_token", "password_reset_expires"])

    logger.info("password_reset_initiated", user_id=str(user.id), email=email)

    # Trigger async notification email
    try:
        from apps.notifications.events import NotificationEvent
        from apps.notifications.tasks import trigger_event_task
        from apps.features import services as feature_services

        frontend_base = str(feature_services.get_setting("site.frontend_url", default="https://aurorablings.com") or "https://aurorablings.com").rstrip("/")
        reset_url = f"{frontend_base}/reset-password?token={token}"
        trigger_event_task.delay(
            event=NotificationEvent.USER_FORGOT_PASSWORD,
            context={
                "user_name": user.get_full_name() or user.email,
                "customer_name": user.get_full_name() or user.email,
                "reset_url": reset_url,
                "token": token,
                "expiry_hours": RESET_TOKEN_EXPIRY_HOURS,
            },
            user_id=str(user.id),
            recipient_email=user.email,
        )
    except Exception:
        logger.exception("password_reset_notification_queue_failed", user_id=str(user.id))

    return token


def confirm_password_reset(*, token: str, new_password: str) -> None:
    """
    Validate the reset token and set the new password.

    Raises:
        NotFoundError: token is invalid or expired.
        ValidationError: new password is too weak.
    """
    _validate_password_strength(new_password)

    token_hash = _hash_token(token)
    user = get_user_by_reset_token(token_hash)

    if not user:
        raise NotFoundError("Password reset link is invalid or has expired.")

    user.set_password(new_password)
    user.password_reset_token   = ""
    user.password_reset_expires = None
    user.failed_login_attempts  = 0
    user.locked_until           = None
    user.save(update_fields=[
        "password", "password_reset_token", "password_reset_expires",
        "failed_login_attempts", "locked_until",
    ])

    logger.info("password_reset_complete", user_id=str(user.id))


# ─────────────────────────────────────────────────────────────
#  Address Management
# ─────────────────────────────────────────────────────────────

def create_address(*, user: User, data: dict) -> Address:
    address_type = data.get("address_type", "shipping")

    # If this is set as default, clear existing default for same type
    if data.get("is_default", False):
        Address.objects.filter(user=user, address_type=address_type, is_default=True).update(is_default=False)

    address = Address.objects.create(user=user, **data)
    logger.info("address_created", user_id=str(user.id), address_id=str(address.id))
    return address


def delete_address(*, address: Address) -> None:
    address_id = str(address.id)
    address.delete()
    logger.info("address_deleted", address_id=address_id)


def unlock_user_account(*, user: User, changed_by=None, request=None) -> User:
    """
    Clear temporary login lock fields so the user can log in immediately.
    """
    was_locked = bool(user.is_locked or user.failed_login_attempts > 0)
    user.failed_login_attempts = 0
    user.last_failed_login = None
    user.locked_until = None
    user.save(update_fields=["failed_login_attempts", "last_failed_login", "locked_until"])

    if was_locked:
        log_activity(
            user=changed_by if changed_by and getattr(changed_by, "is_authenticated", False) else None,
            actor_type=_actor_type_for_user(changed_by),
            action=AuditAction.UPDATE,
            entity_type="auth_lock",
            entity_id=str(user.id),
            description=f"Unlocked account for {user.email}",
            metadata={"target_user_id": str(user.id), "target_email": user.email},
            request=request,
        )
        logger.info(
            "admin_unlocked_user_account",
            admin_id=str(changed_by.id) if changed_by and getattr(changed_by, "id", None) else None,
            target_user_id=str(user.id),
        )
    return user


# ─────────────────────────────────────────────────────────────
#  Private helpers
# ─────────────────────────────────────────────────────────────

def _issue_tokens(user: User) -> dict:
    refresh = RefreshToken.for_user(user)
    refresh["email"] = user.email
    refresh["role"]  = user.role
    return {
        "access":  str(refresh.access_token),
        "refresh": str(refresh),
    }


def _hash_token(token: str) -> str:
    """SHA-256 hash before storing — tokens are one-way in DB."""
    return hashlib.sha256(token.encode()).hexdigest()


def _validate_password_strength(password: str) -> None:
    errors = []
    if len(password) < 8:
        errors.append("Must be at least 8 characters.")
    if not any(c.isupper() for c in password):
        errors.append("Must contain at least one uppercase letter.")
    if not any(c.isdigit() for c in password):
        errors.append("Must contain at least one digit.")
    if errors:
        raise ValidationError("Password is too weak.", extra={"password": errors})


def _record_failed_attempt(user: User) -> None:
    user.failed_login_attempts += 1
    user.last_failed_login = timezone.now()
    was_locked = bool(user.locked_until and timezone.now() < user.locked_until)
    if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
        user.locked_until = timezone.now() + timedelta(minutes=LOCK_DURATION_MINUTES)
    user.save(update_fields=["failed_login_attempts", "last_failed_login", "locked_until"])

    if not was_locked and user.locked_until:
        try:
            from apps.notifications.events import NotificationEvent
            from apps.notifications.tasks import trigger_event_task

            trigger_event_task.delay(
                event=NotificationEvent.USER_BLOCKED,
                context={
                    "user_name": user.get_full_name() or user.email,
                    "customer_name": user.get_full_name() or user.email,
                    "user": {"first_name": (user.first_name or user.get_full_name() or "Customer")},
                    "reason": "Too many failed login attempts",
                    "blocked_hours": round(LOCK_DURATION_MINUTES / 60, 2),
                    "unlock_time": user.locked_until.strftime("%Y-%m-%d %H:%M:%S %Z"),
                    "blocked_until": user.locked_until.strftime("%Y-%m-%d %H:%M:%S %Z"),
                    "reference_id": str(user.id),
                },
                user_id=str(user.id),
                recipient_email=user.email,
            )
        except Exception:
            logger.exception("user_blocked_notification_queue_failed", user_id=str(user.id))


def _reset_failed_attempts(user: User) -> None:
    if user.failed_login_attempts > 0 or user.locked_until:
        user.failed_login_attempts = 0
        user.last_failed_login     = None
        user.locked_until          = None
        user.save(update_fields=["failed_login_attempts", "last_failed_login", "locked_until"])
