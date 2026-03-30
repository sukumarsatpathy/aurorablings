"""
surcharge.views
~~~~~~~~~~~~~~~
Endpoints:

  Public / Customer:
    POST /surcharge/calculate/     → compute surcharges for current cart

  Admin (staff+):
    GET/POST /surcharge/tax/               → list / create tax rules
    GET/PATCH/DELETE /surcharge/tax/{id}/  → detail
    GET/POST /surcharge/shipping/          → list / create shipping rules
    GET/PATCH/DELETE /surcharge/shipping/{id}/
    GET/POST /surcharge/fees/              → list / create fee rules
    GET/PATCH/DELETE /surcharge/fees/{id}/
"""
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from rest_framework.generics import (
    ListCreateAPIView, RetrieveUpdateDestroyAPIView,
)

from apps.accounts.permissions import IsStaffOrAdmin, IsAdminUser
from apps.cart.services import get_or_create_user_cart, get_or_create_guest_cart
from core.response import success_response, error_response
from core.exceptions import NotFoundError

from . import selectors
from .models import TaxRule, ShippingRule, FeeRule
from .services import get_surcharges_for_cart
from .serializers import (
    TaxRuleSerializer, ShippingRuleSerializer, FeeRuleSerializer,
    CartSurchargeRequestSerializer, SurchargeResultSerializer,
)


# ─────────────────────────────────────────────────────────────
#  Calculate surcharges for a cart (public)
# ─────────────────────────────────────────────────────────────

class CartSurchargeView(APIView):
    """
    POST /surcharge/calculate/
    Body: { shipping_address, payment_method?, session_key? }

    Returns the full surcharge breakdown for the current cart,
    including tax, shipping, and fees. Use this to show the
    price breakdown before the customer places the order.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        s = CartSurchargeRequestSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data

        # Resolve cart
        if request.user and request.user.is_authenticated:
            cart = get_or_create_user_cart(request.user)
        else:
            sk = data.get("session_key") or request.headers.get("X-Cart-Token", "")
            if not sk:
                return error_response(
                    message="Provide session_key or X-Cart-Token header.",
                    error_code="no_cart",
                    status_code=400,
                )
            cart = get_or_create_guest_cart(sk)

        if not cart.items.exists():
            return error_response(
                message="Cart is empty.",
                error_code="empty_cart",
                status_code=400,
            )

        result   = get_surcharges_for_cart(
            cart=cart,
            address=data["shipping_address"],
            payment_method=data.get("payment_method", ""),
        )
        return success_response(
            data=result.as_dict(),
            request_id=getattr(request, "request_id", None),
        )


# ─────────────────────────────────────────────────────────────
#  Tax rules (admin CRUD)
# ─────────────────────────────────────────────────────────────

class TaxRuleListCreateView(ListCreateAPIView):
    serializer_class   = TaxRuleSerializer
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def get_queryset(self):
        active_only = self.request.query_params.get("active") == "true"
        return selectors.get_active_tax_rules() if active_only else selectors.get_all_tax_rules()

    def create(self, request, *args, **kwargs):
        s = TaxRuleSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        rule = s.save()
        return success_response(data=TaxRuleSerializer(rule).data, status_code=201)


class TaxRuleDetailView(RetrieveUpdateDestroyAPIView):
    serializer_class   = TaxRuleSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    queryset           = TaxRule.objects.all()
    http_method_names  = ["get", "patch", "delete"]


# ─────────────────────────────────────────────────────────────
#  Shipping rules (admin CRUD)
# ─────────────────────────────────────────────────────────────

class ShippingRuleListCreateView(ListCreateAPIView):
    serializer_class   = ShippingRuleSerializer
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def get_queryset(self):
        active_only = self.request.query_params.get("active") == "true"
        return selectors.get_active_shipping_rules() if active_only else selectors.get_all_shipping_rules()


class ShippingRuleDetailView(RetrieveUpdateDestroyAPIView):
    serializer_class   = ShippingRuleSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    queryset           = ShippingRule.objects.all()
    http_method_names  = ["get", "patch", "delete"]


# ─────────────────────────────────────────────────────────────
#  Fee rules (admin CRUD)
# ─────────────────────────────────────────────────────────────

class FeeRuleListCreateView(ListCreateAPIView):
    serializer_class   = FeeRuleSerializer
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def get_queryset(self):
        active_only = self.request.query_params.get("active") == "true"
        return selectors.get_active_fee_rules() if active_only else selectors.get_all_fee_rules()


class FeeRuleDetailView(RetrieveUpdateDestroyAPIView):
    serializer_class   = FeeRuleSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    queryset           = FeeRule.objects.all()
    http_method_names  = ["get", "patch", "delete"]
