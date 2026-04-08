"""
orders.views
~~~~~~~~~~~~
Endpoint map:

  Customer:
    GET  /orders/              → my orders list
    GET  /orders/{id}/         → my order detail
    POST /orders/              → place order (from cart)
    POST /orders/{id}/cancel/  → cancel own order

  Staff / Admin:
    GET  /orders/admin/            → all orders (filterable)
    POST /orders/{id}/pay/         → mark paid
    POST /orders/{id}/ship/        → mark shipped
    POST /orders/{id}/deliver/     → mark delivered
    POST /orders/{id}/complete/    → mark completed
    POST /orders/{id}/refund/      → mark refunded
    POST /orders/{id}/transition/  → generic transition (admin)
"""
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView

from apps.accounts.permissions import IsStaffOrAdmin
from apps.cart.services import get_or_create_user_cart, get_or_create_guest_cart
from core.response import success_response, error_response
from core.exceptions import NotFoundError
from core.viewsets import BaseViewSet
from core.logging import get_logger

from . import services, selectors
from .serializers import (
    OrderListSerializer, OrderDetailSerializer,
    PlaceOrderSerializer, TransitionSerializer,
    MarkPaidSerializer, MarkShippedSerializer, CancelOrderSerializer,
    AdminOrderCreateSerializer, AdminOrderUpdateSerializer, AdminOrderCalculateSerializer,
)

logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────
#  Helper: resolve cart from request
# ─────────────────────────────────────────────────────────────

def _resolve_cart_for_order(request, session_key: str = ""):
    if request.user and request.user.is_authenticated:
        return get_or_create_user_cart(request.user)
    sk = session_key or request.headers.get("X-Cart-Token", "").strip()
    if sk:
        return get_or_create_guest_cart(sk)
    return None


def _get_order_or_404(order_id, user):
    order = selectors.get_order_by_id(order_id, user=user)
    if not order:
        raise NotFoundError("Order not found.")
    return order


# ─────────────────────────────────────────────────────────────
#  Customer: my orders list + detail
# ─────────────────────────────────────────────────────────────

class MyOrderListView(APIView):
    """GET /orders/  — authenticated user's own orders."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        status_filter = request.query_params.get("status")
        qs = selectors.get_orders_for_user(request.user, status=status_filter)
        serializer = OrderListSerializer(qs, many=True)
        return success_response(
            data=serializer.data,
            request_id=getattr(request, "request_id", None),
        )


class MyOrderDetailView(APIView):
    """GET /orders/{id}/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        order = _get_order_or_404(order_id, request.user)
        return success_response(
            data=OrderDetailSerializer(order).data,
            request_id=getattr(request, "request_id", None),
        )


# ─────────────────────────────────────────────────────────────
#  Place order  (Cart → Order)
# ─────────────────────────────────────────────────────────────

class PlaceOrderView(APIView):
    """
    POST /orders/
    Works for both authenticated users and guests (via session_key in body
    or X-Cart-Token header).
    """
    permission_classes = [AllowAny]

    def post(self, request):
        s = PlaceOrderSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data

        cart = _resolve_cart_for_order(request, data.get("session_key", ""))
        if not cart:
            return error_response(
                message="No active cart found. Provide X-Cart-Token header or session_key.",
                error_code="no_cart",
                status_code=400,
            )

        order, resolved_user = services.checkout_place_order(
            cart=cart,
            shipping_address=data["shipping_address"],
            billing_address=data.get("billing_address"),
            payment_method=data["payment_method"],
            shipping_cost=data["shipping_cost"],
            coupon_code=data.get("coupon_code", ""),
            notes=data.get("notes", ""),
            user=request.user if request.user.is_authenticated else None,
            guest_email=data.get("guest_email", ""),
            warehouse_id=data.get("warehouse_id"),
            changed_by=request.user if request.user.is_authenticated else None,
            create_account=data.get("create_account", False),
            account_data=data.get("account") or {},
            save_address=data.get("save_address", True),
        )
        response_data = OrderDetailSerializer(order).data
        if resolved_user and not request.user.is_authenticated and data.get("create_account", False):
            from apps.accounts.serializers import UserProfileSerializer
            from apps.accounts.services import _issue_tokens

            tokens = _issue_tokens(resolved_user)
            response_data = {
                **response_data,
                "auth": {
                    "access": tokens["access"],
                    "refresh": tokens["refresh"],
                    "user": UserProfileSerializer(resolved_user).data,
                },
            }
        return success_response(
            data=response_data,
            message=f"Order {order.order_number} placed successfully.",
            request_id=getattr(request, "request_id", None),
            status_code=201,
        )


# ─────────────────────────────────────────────────────────────
#  Customer: cancel own order
# ─────────────────────────────────────────────────────────────

class CancelOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, order_id):
        order = _get_order_or_404(order_id, request.user)
        s = CancelOrderSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        order = services.cancel_order(
            order=order,
            changed_by=request.user,
            reason=s.validated_data["reason"],
        )
        return success_response(
            data=OrderDetailSerializer(order).data,
            message="Order cancelled.",
            request_id=getattr(request, "request_id", None),
        )


# ─────────────────────────────────────────────────────────────
#  Admin: all orders
# ─────────────────────────────────────────────────────────────

class AdminOrderListView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def get(self, request):
        qs = selectors.get_all_orders(
            status=request.query_params.get("status"),
            payment_status=request.query_params.get("payment_status"),
            user_id=request.query_params.get("user_id"),
            search=request.query_params.get("search"),
        )
        serializer = OrderListSerializer(qs, many=True)
        return success_response(
            data=serializer.data,
            request_id=getattr(request, "request_id", None),
        )

    def post(self, request):
        s = AdminOrderCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = None
        user_id = s.validated_data.get("user_id")
        if user_id:
            from apps.accounts.models import User
            user = User.objects.filter(id=user_id).first()
            if not user:
                raise NotFoundError("User not found.")
        items = s.validated_data.get("items") or []
        if items:
            order = services.create_admin_order_from_items(
                items=items,
                user=user,
                guest_email=s.validated_data.get("guest_email", ""),
                shipping_address=s.validated_data.get("shipping_address") or {},
                billing_address=s.validated_data.get("billing_address") or {},
                payment_method=s.validated_data.get("payment_method"),
                coupon_code=s.validated_data.get("coupon_code", ""),
                status=s.validated_data.get("status", "placed"),
                notes=s.validated_data.get("notes", ""),
                warehouse_id=s.validated_data.get("warehouse_id"),
                changed_by=request.user,
            )
        else:
            order = services.create_admin_order(
                user=user,
                guest_email=s.validated_data.get("guest_email", ""),
                status=s.validated_data.get("status"),
                payment_status=s.validated_data.get("payment_status"),
                payment_method=s.validated_data.get("payment_method"),
                shipping_address=s.validated_data.get("shipping_address"),
                billing_address=s.validated_data.get("billing_address"),
                subtotal=s.validated_data.get("subtotal"),
                discount_amount=s.validated_data.get("discount_amount"),
                shipping_cost=s.validated_data.get("shipping_cost"),
                tax_amount=s.validated_data.get("tax_amount"),
                grand_total=s.validated_data.get("grand_total"),
                currency=s.validated_data.get("currency", "INR"),
                notes=s.validated_data.get("notes", ""),
                internal_notes=s.validated_data.get("internal_notes", ""),
                changed_by=request.user,
            )
        return success_response(
            data=OrderDetailSerializer(order).data,
            message="Order created.",
            request_id=getattr(request, "request_id", None),
            status_code=201,
        )


class AdminOrderDetailView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def get(self, request, order_id):
        order = selectors.get_order_by_id(order_id)   # no user scoping for admin
        if not order:
            raise NotFoundError("Order not found.")
        return success_response(
            data=OrderDetailSerializer(order).data,
            request_id=getattr(request, "request_id", None),
        )

    def patch(self, request, order_id):
        order = selectors.get_order_by_id(order_id)
        if not order:
            raise NotFoundError("Order not found.")
        s = AdminOrderUpdateSerializer(data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        order = services.update_admin_order(
            order=order,
            changed_by=request.user,
            **s.validated_data,
        )
        return success_response(
            data=OrderDetailSerializer(order).data,
            message="Order updated.",
            request_id=getattr(request, "request_id", None),
        )

    def delete(self, request, order_id):
        order = selectors.get_order_by_id(order_id)
        if not order:
            raise NotFoundError("Order not found.")
        services.delete_admin_order(order=order)
        return success_response(
            message="Order deleted.",
            request_id=getattr(request, "request_id", None),
        )


class AdminOrderSendConfirmationEmailView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request, order_id):
        order = selectors.get_order_by_id(order_id)
        if not order:
            raise NotFoundError("Order not found.")

        recipient_email = (order.user.email if order.user_id and order.user else (order.guest_email or "")).strip()
        if not recipient_email:
            return error_response(
                message="No recipient email found for this order.",
                error_code="missing_recipient_email",
                status_code=400,
            )

        shipping_name = ""
        if isinstance(order.shipping_address, dict):
            shipping_name = str(order.shipping_address.get("full_name", "") or "").strip()
        customer_name = (
            (order.user.get_full_name().strip() if order.user_id and order.user else "")
            or shipping_name
            or (recipient_email.split("@")[0] if recipient_email else "")
            or "Customer"
        )

        try:
            from apps.invoices.services.invoice_service import InvoiceService
            from apps.notifications.events import NotificationEvent
            from apps.notifications.tasks import trigger_event_task

            trigger_event_task.delay(
                event=NotificationEvent.ORDER_CREATED,
                context={
                    **services.build_order_confirmation_email_context(
                        order=order,
                        customer_name=customer_name,
                    ),
                    "invoice_url": InvoiceService.build_public_invoice_url(order_id=str(order.id)),
                },
                user_id=str(order.user_id) if order.user_id else None,
                recipient_email=recipient_email,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("admin_order_confirmation_email_queue_failed", order_id=str(order.id), error=str(exc))
            return error_response(
                message="Failed to queue order confirmation email.",
                error_code="email_queue_failed",
                errors={"detail": str(exc)},
                status_code=500,
            )

        return success_response(
            message="Order confirmation email queued successfully.",
            data={"order_id": str(order.id), "recipient_email": recipient_email},
        )


# ─────────────────────────────────────────────────────────────
#  Admin: lifecycle actions
# ─────────────────────────────────────────────────────────────

class MarkPaidView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request, order_id):
        order = selectors.get_order_by_id(order_id)
        if not order:
            raise NotFoundError("Order not found.")
        s = MarkPaidSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        order = services.mark_paid(order=order, changed_by=request.user, **s.validated_data)
        return success_response(data=OrderDetailSerializer(order).data, message="Order marked as paid.")


class MarkShippedView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request, order_id):
        order = selectors.get_order_by_id(order_id)
        if not order:
            raise NotFoundError("Order not found.")
        s = MarkShippedSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        order = services.mark_shipped(order=order, changed_by=request.user, **s.validated_data)
        return success_response(data=OrderDetailSerializer(order).data, message="Order marked as shipped.")


class MarkDeliveredView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request, order_id):
        order = selectors.get_order_by_id(order_id)
        if not order:
            raise NotFoundError("Order not found.")
        order = services.mark_delivered(order=order, changed_by=request.user)
        return success_response(data=OrderDetailSerializer(order).data, message="Order marked as delivered.")


class MarkCompletedView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request, order_id):
        order = selectors.get_order_by_id(order_id)
        if not order:
            raise NotFoundError("Order not found.")
        order = services.mark_completed(order=order, changed_by=request.user)
        return success_response(data=OrderDetailSerializer(order).data, message="Order completed.")


class MarkRefundedView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request, order_id):
        order = selectors.get_order_by_id(order_id)
        if not order:
            raise NotFoundError("Order not found.")
        reason = request.data.get("reason", "")
        order = services.mark_refunded(order=order, changed_by=request.user, reason=reason)
        return success_response(data=OrderDetailSerializer(order).data, message="Order refunded.")


class GenericTransitionView(APIView):
    """POST /orders/{id}/transition/ — admin-only generic transition."""
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request, order_id):
        order = selectors.get_order_by_id(order_id)
        if not order:
            raise NotFoundError("Order not found.")
        s = TransitionSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        order = services.transition_order(
            order=order,
            new_status=s.validated_data["new_status"],
            changed_by=request.user,
            notes=s.validated_data.get("notes", ""),
        )
        return success_response(data=OrderDetailSerializer(order).data)


class AdminOrderCalculateView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request):
        s = AdminOrderCalculateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = None
        user_id = s.validated_data.get("user_id")
        if user_id:
            from apps.accounts.models import User
            user = User.objects.filter(id=user_id).first()
            if not user:
                raise NotFoundError("User not found.")

        result = services.calculate_admin_order_pricing(
            items=s.validated_data.get("items", []),
            payment_method=s.validated_data.get("payment_method"),
            shipping_address=s.validated_data.get("shipping_address", {}),
            coupon_code=s.validated_data.get("coupon_code", ""),
            user=user,
        )
        return success_response(
            data=result,
            message="Order totals calculated.",
            request_id=getattr(request, "request_id", None),
        )
