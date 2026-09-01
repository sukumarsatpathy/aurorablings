"""
accounts.customer_linking
~~~~~~~~~~~~~~~~~~~~~~~~~

Turning a walk-in into a customer record.

Written as one service on purpose: the counter needs it now, and the website's
guest checkout needs exactly the same thing — given contact details and a paid
order, find or create the customer, link the order, and send the right welcome.
Writing it twice is how you end up with two customer lists that disagree.

Two decisions worth knowing before reading the code:

**Phone is the identity, email is optional.** At an Indian jewellery stall almost
every customer has a number and a meaningful minority have no email they check.
So lookup leads with phone, and an absent email is a perfectly good outcome — the
order keeps the name and number and links to no account. That is a sale, not a
failure.

**No password is ever emailed.** The account is created with an unusable password
and the welcome carries a one-time set-password link. Clicking it is also what
proves the address belongs to the customer — and staff *will* mistype an address
at a busy counter. With a link, a typo is a bounce; with a password in the mail,
a typo is working credentials to a stranger's purchase history.
"""

from __future__ import annotations

import re
import secrets
from datetime import timedelta

import structlog
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import User, UserRole
from apps.accounts.services import _hash_token

logger = structlog.get_logger(__name__)

#: Longer than a password reset: a welcome is often read the next morning, or
#: after a weekend, and an expired link on first contact is a bad introduction.
WELCOME_TOKEN_EXPIRY_DAYS = 7


class CustomerLinkResult:
    """What happened, in terms the caller can act on."""

    def __init__(self, user=None, created=False, conflict=False, reason=""):
        self.user = user
        self.created = created
        self.conflict = conflict
        self.reason = reason

    def __repr__(self):  # pragma: no cover - debugging aid
        return f"<CustomerLinkResult created={self.created} conflict={self.conflict} {self.reason}>"


def phone_digits(raw: str) -> str:
    """Last ten digits — the part that actually identifies an Indian number."""
    digits = re.sub(r"\D", "", str(raw or ""))
    return digits[-10:] if len(digits) >= 10 else digits


def phone_query(raw: str) -> Q:
    """
    Match a number against however it happens to be stored.

    ``User.phone`` is a free-text CharField with no normalisation anywhere in the
    codebase, so the same customer may be on file as ``9876543210``,
    ``+91 98765 43210``, ``09876543210`` or ``+919876543210``. An exact match
    finds one of those and misses the rest, which at a counter looks exactly like
    "the customer isn't in the system" — so staff create a duplicate.

    This matches the common shapes directly and falls back to a suffix match,
    which catches anything with a prefix but no internal spacing. Numbers stored
    with spaces or dashes *inside* them still need the normalisation command to
    be found; see ``normalize_customer_phones``.
    """
    digits = phone_digits(raw)
    if not digits:
        return Q(pk__isnull=True)  # matches nothing

    return (
        Q(phone=raw.strip())
        | Q(phone=digits)
        | Q(phone=f"0{digits}")
        | Q(phone=f"91{digits}")
        | Q(phone=f"+91{digits}")
        | Q(phone=f"+91 {digits}")
        | Q(phone__endswith=digits)
    )


def find_customer(*, phone: str = "", email: str = "") -> CustomerLinkResult:
    """
    Match a walk-in against existing accounts.

    Order matters: phone, then email. `User.phone` carries no uniqueness
    constraint in this schema, so a phone lookup can legitimately return several
    people — a shared family number, or a number typed into two accounts over the
    years. Rather than guess, more than one match is treated as a conflict and
    left for a human.
    """
    phone = (phone or "").strip()
    email = (email or "").strip().lower()

    if phone:
        by_phone = list(User.objects.filter(phone_query(phone), role=UserRole.CUSTOMER)[:2])
        if len(by_phone) > 1:
            return CustomerLinkResult(conflict=True, reason="multiple accounts share this phone number")
        if by_phone:
            user = by_phone[0]
            if email and user.email.lower() != email:
                # The phone says one person, the typed email says another. Never
                # merge automatically — that is how one customer ends up reading
                # another's order history.
                if User.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
                    return CustomerLinkResult(
                        user=user, conflict=True,
                        reason="phone and email belong to different accounts",
                    )
            return CustomerLinkResult(user=user, reason="matched on phone")

    if email:
        by_email = User.objects.filter(email__iexact=email).first()
        if by_email:
            return CustomerLinkResult(user=by_email, reason="matched on email")

    return CustomerLinkResult(reason="no existing account")


def issue_welcome_token(user: User) -> str:
    """
    A one-time link that sets a password and verifies the address in one click.

    Reuses the password-reset token fields and the existing confirm endpoint, so
    there is no second token system to keep secure, and an expired welcome link
    falls back to the ordinary "forgot password" flow with no support call.
    """
    token = secrets.token_urlsafe(32)
    user.password_reset_token = _hash_token(token)
    user.password_reset_expires = timezone.now() + timedelta(days=WELCOME_TOKEN_EXPIRY_DAYS)
    user.save(update_fields=["password_reset_token", "password_reset_expires"])
    return token


@transaction.atomic
def link_or_create_customer(
    *,
    order,
    name: str = "",
    phone: str = "",
    email: str = "",
    create_account: bool = True,
) -> CustomerLinkResult:
    """
    Attach a paid order to a customer, creating the account if there isn't one.

    Called *after* settlement, never before: an abandoned cart or a voided
    part-paid sale must not leave a stranger holding a login.
    """
    phone = (phone or "").strip()
    email = (email or "").strip().lower()

    match = find_customer(phone=phone, email=email)

    if match.conflict:
        logger.warning(
            "customer_link_conflict",
            order_id=str(order.id), reason=match.reason, phone_given=bool(phone),
        )
        if match.user is not None and order.user_id is None:
            order.user = match.user
            order.save(update_fields=["user"])
        return match

    if match.user is not None:
        if order.user_id is None:
            order.user = match.user
            order.save(update_fields=["user"])
        if phone and not match.user.phone:
            match.user.phone = phone
            match.user.save(update_fields=["phone"])
        logger.info("customer_linked", order_id=str(order.id), user_id=str(match.user.id))
        # Deliberately no welcome email: they already have an account, and being
        # welcomed to a shop you've used for a year reads as a mistake.
        return match

    if not create_account or not email:
        # No email means no account, and that is fine — the order keeps the name
        # and number, which is what a stall customer usually wants anyway.
        return CustomerLinkResult(reason="no email; contact kept on the order only")

    first, _, last = (name or "").strip().partition(" ")
    user = User.objects.create_user(
        email=email,
        password=None,
        first_name=first or "Customer",
        last_name=last or "",
        phone=phone,
        role=UserRole.CUSTOMER,
    )
    # No usable password exists until they click the link in the welcome.
    user.set_unusable_password()
    user.save(update_fields=["password"])

    order.user = user
    order.save(update_fields=["user"])

    logger.info("customer_created_from_counter", order_id=str(order.id), user_id=str(user.id))
    return CustomerLinkResult(user=user, created=True, reason="account created")


def send_welcome(*, user: User, order=None) -> bool:
    """Queue the welcome with its set-password link."""
    from apps.features import services as feature_services
    from apps.notifications.events import NotificationEvent
    from apps.notifications.tasks import trigger_event_task

    token = issue_welcome_token(user)
    base = str(
        feature_services.get_setting("site.frontend_url", default="https://aurorablings.com")
        or "https://aurorablings.com"
    ).rstrip("/")

    try:
        trigger_event_task.delay(
            event=NotificationEvent.USER_WELCOME,
            context={
                "user_name": user.get_full_name() or user.email,
                "customer_name": user.get_full_name() or user.email,
                "set_password_url": f"{base}/reset-password?token={token}",
                "expiry_days": WELCOME_TOKEN_EXPIRY_DAYS,
                "order_number": getattr(order, "order_number", ""),
            },
            user_id=str(user.id),
            recipient_email=user.email,
        )
        return True
    except Exception as exc:  # noqa: BLE001 - a mail failure must never fail a paid sale
        logger.warning("welcome_email_queue_failed", user_id=str(user.id), error=str(exc))
        return False
