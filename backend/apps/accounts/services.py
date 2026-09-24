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
import hmac
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
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
from .models import User, Address, LoginAttempt, EmailOTP
from .selectors import get_user_by_email, email_exists, get_user_by_reset_token

logger = get_logger(__name__)

# ── Constants ─────────────────────────────────────────────────
MAX_FAILED_ATTEMPTS = 5        # lock after N consecutive failures
LOCK_DURATION_MINUTES = 30     # how long the lock lasts
RESET_TOKEN_EXPIRY_HOURS = 2   # password reset link lifetime

# Email OTP sign-in
OTP_LENGTH = 6
OTP_EXPIRY_MINUTES = 10          # code lifetime
OTP_MAX_VERIFY_ATTEMPTS = 5      # wrong guesses before the code is burned
OTP_RESEND_COOLDOWN_SECONDS = 60 # min gap between two sends to one email
OTP_MAX_SENDS_PER_HOUR = 5       # per email address


class OTPCooldownError(Exception):
    """Raised when an OTP is requested again too soon for the same email."""

    def __init__(self, retry_after: int):
        self.retry_after = max(1, int(retry_after))
        super().__init__(f"Please wait {self.retry_after} seconds before requesting a new code.")


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


def issue_auth_tokens(*, user: User) -> dict:
    """
    Return a fresh JWT pair for an already-authenticated user lifecycle event,
    such as immediate sign-in right after registration.
    """
    return _issue_tokens(user)


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
#  Email OTP sign-in
# ─────────────────────────────────────────────────────────────

def request_login_otp(*, email: str, ip_address: str | None = None) -> None:
    """
    Issue a one-time sign-in code and queue the email.

    Existing, active accounts only. For unknown / inactive / locked emails
    this is a silent no-op so the endpoint cannot be used to discover which
    addresses are registered. The per-email cooldown is applied to *every*
    address — registered or not — for the same reason.

    Raises:
        OTPCooldownError: a code was sent to this email too recently.
    """
    email = email.strip().lower()
    _enforce_otp_send_limits(email)

    user = get_user_by_email(email)
    if not user:
        logger.info("login_otp_noop", email=email, reason="user_not_found", ip=ip_address)
        return
    if not user.is_active:
        logger.info("login_otp_noop", email=email, reason="account_inactive", ip=ip_address)
        return
    if user.is_locked:
        logger.info("login_otp_noop", email=email, reason="account_locked", ip=ip_address)
        return

    code = f"{secrets.randbelow(10 ** OTP_LENGTH):0{OTP_LENGTH}d}"

    with transaction.atomic():
        # One live code per user: a new request invalidates any earlier one.
        EmailOTP.objects.filter(user=user, purpose=EmailOTP.PURPOSE_LOGIN).delete()
        otp = EmailOTP.objects.create(
            user=user,
            email=user.email,
            purpose=EmailOTP.PURPOSE_LOGIN,
            code_hash=_hash_otp(user.email, code),
            expires_at=timezone.now() + timedelta(minutes=OTP_EXPIRY_MINUTES),
            ip_address=ip_address,
        )

    logger.info("login_otp_issued", user_id=str(user.id), otp_id=str(otp.id), ip=ip_address)

    try:
        from .tasks import send_login_otp_email
        send_login_otp_email.delay(
            user_id=str(user.id),
            code=code,
            expiry_minutes=OTP_EXPIRY_MINUTES,
        )
    except Exception:
        logger.exception("login_otp_email_queue_failed", user_id=str(user.id))


def verify_login_otp(
    *,
    email: str,
    code: str,
    ip_address: str | None = None,
    user_agent: str = "",
    request=None,
) -> dict:
    """
    Check a sign-in code and return JWT tokens on success.

    Raises:
        ValidationError: code wrong, expired, or already used.
        PermissionDeniedError: account locked or deactivated.

    Returns:
        {"access": "...", "refresh": "...", "user": User}
    """
    email = email.strip().lower()
    code = (code or "").strip()
    invalid_msg = "Invalid or expired code. Please request a new one."

    def _log_attempt(successful: bool, reason: str = ""):
        LoginAttempt.objects.create(
            email=email,
            ip_address=ip_address,
            user_agent=user_agent,
            successful=successful,
            failure_reason=reason,
        )

    user = get_user_by_email(email)
    if not user:
        _log_attempt(False, "otp_user_not_found")
        logger.warning("login_otp_failed", email=email, reason="user_not_found", ip=ip_address)
        raise ValidationError(invalid_msg)

    # Errors are decided inside the lock but raised after it commits —
    # raising inside atomic() would roll back the attempt counter.
    failure: str | None = None
    with transaction.atomic():
        otp = (
            EmailOTP.objects
            .select_for_update()
            .filter(user=user, purpose=EmailOTP.PURPOSE_LOGIN, consumed_at__isnull=True)
            .order_by("-created_at")
            .first()
        )

        if not otp or not otp.is_usable:
            failure = "expired_or_missing"
        elif otp.attempts >= OTP_MAX_VERIFY_ATTEMPTS:
            otp.consumed_at = timezone.now()
            otp.save(update_fields=["consumed_at"])
            failure = "too_many_attempts"
        elif not hmac.compare_digest(otp.code_hash, _hash_otp(user.email, code)):
            otp.attempts += 1
            if otp.attempts >= OTP_MAX_VERIFY_ATTEMPTS:
                otp.consumed_at = timezone.now()
                failure = "too_many_attempts"
            else:
                failure = "wrong_code"
            otp.save(update_fields=["attempts", "consumed_at"])
        else:
            # Correct — burn it so it can never be replayed.
            otp.consumed_at = timezone.now()
            otp.save(update_fields=["consumed_at"])

    if failure:
        _log_attempt(False, f"otp_{failure}")
        log_activity(
            user=user,
            actor_type=_actor_type_for_user(user),
            action=AuditAction.LOGIN,
            entity_type="auth",
            entity_id=str(user.id),
            description=f"OTP login failed: {failure.replace('_', ' ')}",
            metadata={"email": email, "method": "email_otp", "reason": failure, "status": "failed"},
            request=request,
        )
        logger.warning("login_otp_failed", user_id=str(user.id), reason=failure, ip=ip_address)
        if failure == "wrong_code":
            remaining = OTP_MAX_VERIFY_ATTEMPTS - otp.attempts
            raise ValidationError(f"Incorrect code. {remaining} attempt(s) remaining.")
        if failure == "too_many_attempts":
            raise ValidationError("Too many incorrect attempts. Please request a new code.")
        raise ValidationError(invalid_msg)

    if user.is_locked:
        _log_attempt(False, "account_locked")
        raise PermissionDeniedError(
            f"Account locked due to too many failed attempts. "
            f"Try again after {user.locked_until.strftime('%H:%M UTC')}."
        )
    if not user.is_active:
        _log_attempt(False, "account_inactive")
        raise PermissionDeniedError("This account has been deactivated.")

    # Receiving the code proves the mailbox belongs to this user.
    if not user.is_email_verified:
        user.is_email_verified = True
        user.save(update_fields=["is_email_verified"])

    _reset_failed_attempts(user)
    _log_attempt(True)
    log_activity(
        user=user,
        actor_type=_actor_type_for_user(user),
        action=AuditAction.LOGIN,
        entity_type="auth",
        entity_id=str(user.id),
        description=f"{user.role.title()} logged in with email OTP",
        metadata={"email": email, "method": "email_otp", "status": "success"},
        request=request,
    )

    tokens = _issue_tokens(user)
    logger.info("login_otp_success", user_id=str(user.id), email=email, ip=ip_address)
    return {**tokens, "user": user}


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
    data = normalise_address_payload(data)
    address_type = data.get("address_type", "shipping")

    # If this is set as default, clear existing default for same type
    if data.get("is_default", False):
        Address.objects.filter(user=user, address_type=address_type, is_default=True).update(is_default=False)

    address = Address.objects.create(user=user, **data)
    logger.info("address_created", user_id=str(user.id), address_id=str(address.id))
    log_activity(
        user=user,
        actor_type=_actor_type_for_user(user),
        action=AuditAction.CREATE,
        entity_type="address",
        entity_id=str(address.id),
        description=f"Created {address_type} address",
        metadata={"address_type": address_type, "is_default": address.is_default},
    )
    return address


def normalise_address_payload(data: dict | None) -> dict:
    payload = dict(data or {})
    address_line1 = payload.pop("address_line1", None)
    address_line2 = payload.pop("address_line2", None)
    postal_code = payload.pop("postal_code", None)
    pincode = payload.pop("pincode", None)

    if address_line1 is not None and not payload.get("line1"):
        payload["line1"] = address_line1
    if address_line2 is not None and not payload.get("line2"):
        payload["line2"] = address_line2
    if postal_code is not None and not payload.get("postal_code"):
        payload["postal_code"] = postal_code
    if pincode is not None and not payload.get("postal_code"):
        payload["postal_code"] = pincode
    return payload


@transaction.atomic
def update_address(*, address: Address, data: dict, changed_by=None) -> Address:
    payload = normalise_address_payload(data)
    address_type = payload.get("address_type", address.address_type)
    make_default = bool(payload.get("is_default", address.is_default))

    if make_default:
        Address.objects.filter(
            user=address.user,
            address_type=address_type,
            is_default=True,
        ).exclude(id=address.id).update(is_default=False)

    for field, value in payload.items():
        setattr(address, field, value)
    address.save()

    actor = changed_by if changed_by and getattr(changed_by, "is_authenticated", False) else address.user
    log_activity(
        user=actor,
        actor_type=_actor_type_for_user(actor),
        action=AuditAction.UPDATE,
        entity_type="address",
        entity_id=str(address.id),
        description=f"Updated {address.address_type} address",
        metadata={"address_type": address.address_type, "is_default": address.is_default},
    )
    return address


@transaction.atomic
def save_checkout_address(
    *,
    user: User,
    address_data: dict,
    address_type: str = "shipping",
    set_default: bool = True,
    changed_by=None,
) -> Address:
    payload = normalise_address_payload(address_data)
    payload["address_type"] = address_type
    payload["is_default"] = set_default

    existing = None
    if set_default:
        existing = (
            Address.objects
            .select_for_update()
            .filter(user=user, address_type=address_type, is_default=True)
            .first()
        )

    if existing:
        return update_address(address=existing, data=payload, changed_by=changed_by or user)
    return create_address(user=user, data=payload)


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


def _hash_otp(email: str, code: str) -> str:
    """Keyed hash so a leaked DB row cannot be brute-forced offline (only 10^6 codes)."""
    message = f"{email.strip().lower()}:{code}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), message, hashlib.sha256).hexdigest()


def _enforce_otp_send_limits(email: str) -> None:
    """Per-email resend cooldown + hourly cap, applied to every address."""
    key_id = hashlib.sha256(email.encode()).hexdigest()
    cooldown_key = f"auth:otp:cooldown:{key_id}"
    hourly_key = f"auth:otp:hourly:{key_id}"

    if not cache.add(cooldown_key, 1, timeout=OTP_RESEND_COOLDOWN_SECONDS):
        ttl = OTP_RESEND_COOLDOWN_SECONDS
        try:
            ttl = cache.ttl(cooldown_key) or ttl   # django-redis only
        except Exception:  # noqa: BLE001
            pass
        raise OTPCooldownError(ttl)

    cache.add(hourly_key, 0, timeout=3600)
    try:
        sends = cache.incr(hourly_key)
    except ValueError:
        cache.set(hourly_key, 1, timeout=3600)
        sends = 1
    if sends > OTP_MAX_SENDS_PER_HOUR:
        ttl = 3600
        try:
            ttl = cache.ttl(hourly_key) or ttl
        except Exception:  # noqa: BLE001
            pass
        raise OTPCooldownError(ttl)


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
