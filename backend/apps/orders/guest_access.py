"""
orders.guest_access
~~~~~~~~~~~~~~~~~~~

Letting a shopper with no account pay for, look at, and cancel *their own*
order — and nobody else's.

A logged-in customer proves ownership with their JWT. A guest has nothing, so
placing a guest order hands back a signed token bound to that one order id. The
storefront keeps it in session storage and sends it as ``X-Guest-Order-Token``
on the handful of endpoints a guest checkout needs (create the Razorpay order,
verify the payment, reconcile, read the order, cancel it on a dismissed
checkout). Nothing else accepts it.

Why a signed token and not "the order id is secret enough": order ids appear in
URLs, logs and emails. A token is useless without the server's SECRET_KEY,
expires on its own, and only ever matches an order that has no owner — so it can
never be used to reach a registered customer's order.
"""

from __future__ import annotations

from django.core import signing

from core.exceptions import NotFoundError

SALT = "orders.guest-order-access.v1"
#: Long enough to pay, come back from a bank redirect and see the thank-you page;
#: short enough that a leaked token goes stale. Guests track later by order
#: number + phone, not with this.
MAX_AGE_SECONDS = 60 * 60 * 24 * 2

HEADER = "X-Guest-Order-Token"


def guest_checkout_enabled() -> bool:
    """Admin kill-switch. Off means checkout behaves exactly as it did before."""
    from apps.features.services import get_setting

    value = get_setting("checkout_guest_enabled", default=True)
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes")
    return bool(value)


def issue_token(order) -> str:
    """Only ever for an order nobody owns."""
    if order.user_id:
        return ""
    return signing.dumps({"o": str(order.id)}, salt=SALT, compress=True)


def _token_from(request) -> str:
    token = (request.headers.get(HEADER) or "").strip()
    if not token:
        data = getattr(request, "data", None)
        if hasattr(data, "get"):
            token = str(data.get("guest_token") or "").strip()
    return token


def token_order_id(request) -> str | None:
    """The order id the request's guest token vouches for, or None."""
    token = _token_from(request)
    if not token:
        return None
    try:
        payload = signing.loads(token, salt=SALT, max_age=MAX_AGE_SECONDS)
    except signing.BadSignature:  # includes SignatureExpired
        return None
    order_id = payload.get("o") if isinstance(payload, dict) else None
    return str(order_id) if order_id else None


def get_guest_order_or_404(request, order_id):
    """
    The order, if and only if this request carries a valid guest token for it
    and the order is still a guest order.

    Every failure is the same 404, so the endpoint never confirms that an order
    id exists to someone who can't prove they own it.
    """
    from apps.orders import selectors

    vouched = token_order_id(request)
    if not vouched or vouched != str(order_id):
        raise NotFoundError("Order not found.")

    order = selectors.get_order_by_id(order_id)
    if not order or order.user_id:
        raise NotFoundError("Order not found.")
    return order


def request_is_authenticated(request) -> bool:
    user = getattr(request, "user", None)
    return bool(user and user.is_authenticated)
