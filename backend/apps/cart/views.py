"""
cart.views
~~~~~~~~~~
Cart identification via request:
  - Authenticated user   → cart resolved by request.user
  - Anonymous visitor    → cart resolved by X-Cart-Token header
                           (UUID generated client-side on first visit)

All endpoints return the full CartReadSerializer response on success so
the client always has the latest cart state after any mutation.
"""
from decimal import Decimal

from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from core.response import success_response, error_response
from core.exceptions import NotFoundError, ValidationError as CoreValidationError
from core.logging import get_logger
from apps.pricing.services import PricingService
from apps.pricing.models import Coupon
from apps.pricing.coupons.services import CouponService

from . import services, selectors
from .serializers import (
    CartReadSerializer, AddItemSerializer,
    UpdateItemSerializer, MergeCartSerializer,
)

logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────
#  Helper: resolve cart from request
# ─────────────────────────────────────────────────────────────

def _resolve_cart(request):
    """
    Return the appropriate cart for the request.

    Precedence:
      1. Authenticated user → user cart
      2. X-Cart-Token header → guest cart
      3. Neither → None
    """
    if request.user and request.user.is_authenticated:
        return services.get_or_create_user_cart(request.user)

    session_key = request.headers.get("X-Cart-Token", "").strip()
    if session_key:
        return services.get_or_create_guest_cart(session_key)

    return None


def _coupon_code_from_request(request) -> str:
    query_code = request.query_params.get("coupon_code", "").strip()
    if query_code:
        return query_code
    body_code = request.data.get("coupon_code", "") if hasattr(request, "data") else ""
    return str(body_code).strip() if body_code else ""


def _cart_response(cart, request=None, message=None, coupon_code: str = ""):
    """Build a standardised cart success response including totals."""
    resolved_coupon_code = coupon_code or getattr(cart, "coupon_code", "")
    pricing = PricingService.calculate(
        cart=cart,
        coupon_code=resolved_coupon_code or None,
        user=request.user if request and request.user.is_authenticated else None,
        request=request,
    )
    totals = pricing["cart_totals"]
    return success_response(
        data={
            "cart_id":         str(cart.id),
            "session_key":     cart.session_key,   # None for user carts
            "status":          cart.status,
            "is_guest":        cart.is_guest,
            "item_count":      totals["item_count"],
            "line_count":      totals["line_count"],
            "subtotal":        str(totals["subtotal"]),
            "original_subtotal": str(totals["original_subtotal"]),
            "savings":         str(totals["savings"]),
            "coupon_code":     pricing["coupon"]["code"] if pricing["coupon"] else (resolved_coupon_code or None),
            "discount":        str(pricing["discount"]),
            "total":           str(pricing["total"]),
            "coupon":          (
                {
                    "code": pricing["coupon"]["code"],
                    "type": pricing["coupon"]["type"],
                    "amount": str(pricing["coupon"]["amount"]),
                }
                if pricing["coupon"] else None
            ),
            "items":           totals["items"],
        },
        message=message,
        request_id=getattr(request, "request_id", None),
    )


def _coupon_error_message(exc: Exception) -> str:
    detail = getattr(exc, "detail", None)
    if isinstance(detail, dict):
        return "; ".join(str(value) for value in detail.values())
    if isinstance(detail, (list, tuple)):
        return "; ".join(str(value) for value in detail)
    return str(detail or exc)


def _serialize_coupon_option(*, coupon, cart, user, applied_code: str) -> dict:
    is_eligible = True
    disabled_reason = ""
    estimated_discount = Decimal("0")

    try:
        CouponService.validate_coupon(coupon=coupon, user=user, cart=cart)
        estimated_discount = CouponService.calculate_discount(coupon=coupon, cart=cart)
    except CoreValidationError as exc:
        is_eligible = False
        disabled_reason = _coupon_error_message(exc)

    return {
        "id": str(coupon.id),
        "code": coupon.code,
        "discount_type": coupon.type,
        "value": str(coupon.value),
        "max_discount": str(coupon.max_discount) if coupon.max_discount is not None else None,
        "min_order_amount": str(coupon.min_order_value),
        "usage_limit": coupon.usage_limit,
        "per_user_limit": coupon.per_user_limit,
        "valid_from": coupon.start_date.isoformat(),
        "valid_to": coupon.end_date.isoformat(),
        "is_active": coupon.is_active,
        "is_eligible": is_eligible,
        "disabled_reason": disabled_reason,
        "estimated_discount": str(estimated_discount),
        "is_applied": coupon.code.upper() == applied_code.upper() if applied_code else False,
    }


# ─────────────────────────────────────────────────────────────
#  GET /cart/   — retrieve cart
# ─────────────────────────────────────────────────────────────

class CartView(APIView):
    """
    GET  /cart/     → retrieve current cart with totals
    DELETE /cart/   → clear all items
    """
    permission_classes = [AllowAny]

    def get(self, request):
        cart = _resolve_cart(request)
        coupon_code = _coupon_code_from_request(request)
        if not cart:
            # Return an empty cart shape rather than 401
            return success_response(
                data={
                    "cart_id": None,
                    "item_count": 0,
                    "subtotal": "0.00",
                    "discount": "0.00",
                    "total": "0.00",
                    "coupon_code": coupon_code or None,
                    "coupon": None,
                    "items": [],
                },
                request_id=getattr(request, "request_id", None),
            )
        return _cart_response(cart, request, coupon_code=coupon_code)

    def delete(self, request):
        cart = _resolve_cart(request)
        coupon_code = _coupon_code_from_request(request)
        if not cart:
            raise NotFoundError("No active cart.")
        services.clear_cart(cart=cart)
        return _cart_response(cart, request, message="Cart cleared.", coupon_code=coupon_code)


# ─────────────────────────────────────────────────────────────
#  POST /cart/items/   — add item
# ─────────────────────────────────────────────────────────────

class CartItemAddView(APIView):
    """
    POST /cart/items/
    Body: { variant_id, quantity, warehouse_id? }
    """
    permission_classes = [AllowAny]

    def post(self, request):
        cart = _resolve_cart(request)
        if not cart:
            return error_response(
                message="Provide an X-Cart-Token header for guest carts.",
                error_code="no_cart_token",
                status_code=400,
            )

        s = AddItemSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        services.add_item(
            cart=cart,
            variant_id=s.validated_data["variant_id"],
            quantity=s.validated_data["quantity"],
            warehouse_id=s.validated_data.get("warehouse_id"),
        )
        return _cart_response(
            cart,
            request,
            message="Item added to cart.",
            coupon_code=s.validated_data.get("coupon_code", ""),
        )


# ─────────────────────────────────────────────────────────────
#  PATCH /cart/items/{item_id}/   — update qty
# DELETE /cart/items/{item_id}/   — remove item
# ─────────────────────────────────────────────────────────────

class CartItemDetailView(APIView):
    """
    PATCH  /cart/items/{item_id}/  → set quantity
    DELETE /cart/items/{item_id}/  → remove item
    """
    permission_classes = [AllowAny]

    def patch(self, request, item_id):
        cart = _resolve_cart(request)
        if not cart:
            raise NotFoundError("No active cart.")

        s = UpdateItemSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        services.update_item(
            cart=cart,
            item_id=item_id,
            quantity=s.validated_data["quantity"],
            warehouse_id=s.validated_data.get("warehouse_id"),
        )
        return _cart_response(
            cart,
            request,
            message="Cart updated.",
            coupon_code=s.validated_data.get("coupon_code", ""),
        )

    def delete(self, request, item_id):
        cart = _resolve_cart(request)
        coupon_code = _coupon_code_from_request(request)
        if not cart:
            raise NotFoundError("No active cart.")

        services.remove_item(cart=cart, item_id=item_id)
        return _cart_response(cart, request, message="Item removed.", coupon_code=coupon_code)


# ─────────────────────────────────────────────────────────────
#  POST /cart/merge/   — merge guest cart into user cart on login
# ─────────────────────────────────────────────────────────────

class CartMergeView(APIView):
    """
    POST /cart/merge/
    Body: { session_key: "..." }
    Requires authentication — called immediately after login.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        s = MergeCartSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        cart = services.merge_guest_cart(
            user=request.user,
            session_key=s.validated_data["session_key"],
        )
        return _cart_response(cart, request, message="Guest cart merged.")


# ─────────────────────────────────────────────────────────────
#  POST /cart/validate/   — pre-checkout stock + price check
# ─────────────────────────────────────────────────────────────

class CartValidateView(APIView):
    """
    POST /cart/validate/
    Runs stock + price checks. Returns 200 with errors list.
    An empty errors list means the cart is ready for checkout.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        cart = _resolve_cart(request)
        if not cart:
            raise NotFoundError("No active cart.")

        warehouse_id = request.data.get("warehouse_id")
        errors       = services.validate_cart(cart=cart, warehouse_id=warehouse_id)
        coupon_code  = _coupon_code_from_request(request)
        pricing = PricingService.calculate(
            cart=cart,
            coupon_code=coupon_code or None,
            user=request.user if request.user.is_authenticated else None,
            request=request,
        )

        return success_response(
            data={
                "valid":  len(errors) == 0,
                "errors": errors,
                "coupon_code": pricing["coupon"]["code"] if pricing["coupon"] else None,
                "discount": str(pricing["discount"]),
                "total": str(pricing["total"]),
            },
            message="Cart is valid." if not errors else "Cart has issues that need resolving.",
            request_id=getattr(request, "request_id", None),
        )


class CartApplyCouponView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        cart = _resolve_cart(request)
        if not cart:
            raise NotFoundError("No active cart.")

        coupon_code = str(request.data.get("coupon_code", "") or "").strip()
        if not coupon_code:
            return error_response(
                message="Coupon code is required.",
                error_code="coupon_code_required",
                status_code=400,
            )

        services.apply_coupon(
            cart=cart,
            coupon_code=coupon_code,
            user=request.user if request.user.is_authenticated else None,
            request=request,
        )
        return _cart_response(cart, request, message="Coupon applied.", coupon_code=coupon_code)


class CartRemoveCouponView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        cart = _resolve_cart(request)
        if not cart:
            raise NotFoundError("No active cart.")

        services.remove_coupon(
            cart=cart,
            user=request.user if request.user.is_authenticated else None,
            request=request,
        )
        return _cart_response(cart, request, message="Coupon removed.")


class CartCouponListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        cart = _resolve_cart(request)
        if not cart:
            return success_response(
                data={
                    "coupons": [],
                    "applied_coupon_code": None,
                },
                request_id=getattr(request, "request_id", None),
            )

        queryset = Coupon.objects.filter(is_active=True).order_by("-created_at")
        applied_code = str(getattr(cart, "coupon_code", "") or "").strip()
        user = request.user if request.user.is_authenticated else None
        coupons = [
            _serialize_coupon_option(coupon=coupon, cart=cart, user=user, applied_code=applied_code)
            for coupon in queryset
        ]
        return success_response(
            data={
                "coupons": coupons,
                "applied_coupon_code": applied_code or None,
            },
            request_id=getattr(request, "request_id", None),
        )
