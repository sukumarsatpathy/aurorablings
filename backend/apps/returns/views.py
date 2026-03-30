"""
returns.views
~~~~~~~~~~~~~
Customer:
  POST /returns/                    → create return request
  GET  /returns/                    → my returns
  GET  /returns/{id}/               → return detail
  POST /exchanges/                  → create exchange request
  GET  /exchanges/                  → my exchanges
  GET  /exchanges/{id}/             → exchange detail

Admin (staff+):
  GET  /returns/admin/                          → all returns
  POST /returns/admin/{id}/approve/             → approve
  POST /returns/admin/{id}/reject/              → reject
  POST /returns/admin/{id}/receive/             → mark items received
  POST /returns/admin/{id}/inspect/             → inspect + set conditions
  POST /returns/admin/{id}/reintegrate-stock/   → push to inventory
  POST /returns/admin/{id}/initiate-refund/     → mark refund initiated
  POST /returns/admin/{id}/complete/            → complete
  POST /returns/admin/{id}/reject-inspection/   → reject after inspection

  GET  /exchanges/admin/                        → all exchanges
  POST /exchanges/admin/{id}/approve/
  POST /exchanges/admin/{id}/reject/
  POST /exchanges/admin/{id}/receive/
  POST /exchanges/admin/{id}/inspect/
  POST /exchanges/admin/{id}/reintegrate-stock/
  POST /exchanges/admin/{id}/ship/              → ship replacement
  POST /exchanges/admin/{id}/complete/

  GET/PATCH /policy/                → view / update return policy
"""
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView

from apps.accounts.permissions import IsStaffOrAdmin
from apps.orders.selectors import get_order_by_id
from core.response import success_response, error_response
from core.exceptions import NotFoundError
from core.logging import get_logger

from . import services, selectors
from .models import ReturnPolicy
from .serializers import (
    ReturnRequestSerializer, ExchangeRequestSerializer,
    CreateReturnSerializer, CreateExchangeSerializer,
    AdminCreateReturnSerializer, AdminCreateExchangeSerializer,
    UpdateReturnSerializer, UpdateExchangeSerializer,
    InspectItemsSerializer, MarkReceivedSerializer,
    RejectSerializer, ShipExchangeSerializer,
    ReturnPolicySerializer,
)

logger = get_logger(__name__)


def _get_return_or_404(rr_id, user):
    rr = selectors.get_return_by_id(rr_id, user=user)
    if not rr:
        raise NotFoundError("Return request not found.")
    return rr


def _get_exchange_or_404(exc_id, user):
    exc = selectors.get_exchange_by_id(exc_id, user=user)
    if not exc:
        raise NotFoundError("Exchange request not found.")
    return exc


# ─────────────────────────────────────────────────────────────
#  Customer: Returns
# ─────────────────────────────────────────────────────────────

class MyReturnListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = selectors.get_returns_for_user(request.user)
        return success_response(data=ReturnRequestSerializer(qs, many=True).data)

    def post(self, request):
        s = CreateReturnSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data

        order = get_order_by_id(data["order_id"], user=request.user)
        if not order:
            raise NotFoundError("Order not found.")

        rr = services.create_return_request(
            order=order, user=request.user,
            items_data=data["items"],
            notes=data.get("notes", ""),
            pickup_address=data.get("pickup_address"),
        )
        return success_response(
            data=ReturnRequestSerializer(rr).data,
            message=f"Return request {rr.return_number} submitted.",
            status_code=201,
        )


class MyReturnDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, rr_id):
        rr = _get_return_or_404(rr_id, request.user)
        return success_response(data=ReturnRequestSerializer(rr).data)


# ─────────────────────────────────────────────────────────────
#  Customer: Exchanges
# ─────────────────────────────────────────────────────────────

class MyExchangeListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = selectors.get_exchanges_for_user(request.user)
        return success_response(data=ExchangeRequestSerializer(qs, many=True).data)

    def post(self, request):
        s = CreateExchangeSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data

        order = get_order_by_id(data["order_id"], user=request.user)
        if not order:
            raise NotFoundError("Order not found.")

        exc = services.create_exchange_request(
            order=order, user=request.user,
            items_data=data["items"],
            notes=data.get("notes", ""),
            shipping_address=data.get("shipping_address"),
        )
        return success_response(
            data=ExchangeRequestSerializer(exc).data,
            message=f"Exchange request {exc.exchange_number} submitted.",
            status_code=201,
        )


class MyExchangeDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, exc_id):
        exc = _get_exchange_or_404(exc_id, request.user)
        return success_response(data=ExchangeRequestSerializer(exc).data)


# ─────────────────────────────────────────────────────────────
#  Admin: Return actions
# ─────────────────────────────────────────────────────────────

class AdminReturnListView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def get(self, request):
        qs = selectors.get_all_returns(
            status=request.query_params.get("status"),
            is_refund_ready=request.query_params.get("refund_ready") == "true" or None,
            order_id=request.query_params.get("order_id"),
        )
        return success_response(data=ReturnRequestSerializer(qs, many=True).data)

    def post(self, request):
        s = AdminCreateReturnSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data

        order = get_order_by_id(data["order_id"])
        if not order:
            raise NotFoundError("Order not found.")

        user = order.user
        user_id = data.get("user_id")
        if user_id:
            from apps.accounts.models import User
            user = User.objects.filter(id=user_id).first()

        rr = services.create_return_request(
            order=order,
            user=user,
            items_data=data["items"],
            notes=data.get("notes", ""),
            pickup_address=data.get("pickup_address"),
        )
        return success_response(
            data=ReturnRequestSerializer(rr).data,
            message=f"Return request {rr.return_number} created.",
            status_code=201,
        )


class AdminReturnDetailView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def get(self, request, rr_id):
        rr = _get_return_or_404(rr_id, request.user)
        return success_response(data=ReturnRequestSerializer(rr).data)

    def patch(self, request, rr_id):
        rr = _get_return_or_404(rr_id, request.user)
        s = UpdateReturnSerializer(data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        rr = services.update_return_request(rr=rr, **s.validated_data)
        return success_response(data=ReturnRequestSerializer(rr).data, message="Return updated.")

    def delete(self, request, rr_id):
        rr = _get_return_or_404(rr_id, request.user)
        services.delete_return_request(rr=rr)
        return success_response(message="Return deleted.")


class AdminReturnApproveView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request, rr_id):
        rr = _get_return_or_404(rr_id, request.user)
        rr = services.approve_return(rr=rr, changed_by=request.user, notes=request.data.get("notes", ""))
        return success_response(data=ReturnRequestSerializer(rr).data, message="Return approved.")


class AdminReturnRejectView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request, rr_id):
        rr = _get_return_or_404(rr_id, request.user)
        s  = RejectSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        rr = services.reject_return(rr=rr, changed_by=request.user, reason=s.validated_data["reason"])
        return success_response(data=ReturnRequestSerializer(rr).data, message="Return rejected.")


class AdminReturnReceiveView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request, rr_id):
        rr = _get_return_or_404(rr_id, request.user)
        s  = MarkReceivedSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        rr = services.mark_items_received(rr=rr, changed_by=request.user, **s.validated_data)
        return success_response(data=ReturnRequestSerializer(rr).data, message="Items received.")


class AdminReturnInspectView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request, rr_id):
        rr = _get_return_or_404(rr_id, request.user)
        s  = InspectItemsSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        rr = services.inspect_return_items(
            rr=rr, changed_by=request.user, **s.validated_data
        )
        return success_response(
            data=ReturnRequestSerializer(rr).data,
            message=f"Inspection complete. Refund amount: {rr.refund_amount}.",
        )


class AdminReturnReintegrateView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request, rr_id):
        rr = _get_return_or_404(rr_id, request.user)
        rr = services.reintegrate_stock_for_return(rr=rr, changed_by=request.user)
        return success_response(data=ReturnRequestSerializer(rr).data, message="Stock reintegrated.")


class AdminReturnInitiateRefundView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request, rr_id):
        rr = _get_return_or_404(rr_id, request.user)
        rr = services.initiate_refund_for_return(rr=rr, changed_by=request.user)
        return success_response(data=ReturnRequestSerializer(rr).data, message="Refund initiated.")


class AdminReturnCompleteView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request, rr_id):
        rr = _get_return_or_404(rr_id, request.user)
        rr = services.complete_return(rr=rr, changed_by=request.user)
        return success_response(data=ReturnRequestSerializer(rr).data, message="Return completed.")


class AdminReturnRejectAfterInspectionView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request, rr_id):
        rr = _get_return_or_404(rr_id, request.user)
        s  = RejectSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        rr = services.reject_after_inspection(rr=rr, reason=s.validated_data["reason"], changed_by=request.user)
        return success_response(data=ReturnRequestSerializer(rr).data, message="Rejected after inspection.")


# ─────────────────────────────────────────────────────────────
#  Admin: Exchange actions
# ─────────────────────────────────────────────────────────────

class AdminExchangeListView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def get(self, request):
        qs = selectors.get_all_exchanges(
            status=request.query_params.get("status"),
            order_id=request.query_params.get("order_id"),
        )
        return success_response(data=ExchangeRequestSerializer(qs, many=True).data)

    def post(self, request):
        s = AdminCreateExchangeSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data

        order = get_order_by_id(data["order_id"])
        if not order:
            raise NotFoundError("Order not found.")

        user = order.user
        user_id = data.get("user_id")
        if user_id:
            from apps.accounts.models import User
            user = User.objects.filter(id=user_id).first()

        exc = services.create_exchange_request(
            order=order,
            user=user,
            items_data=data["items"],
            notes=data.get("notes", ""),
            shipping_address=data.get("shipping_address"),
        )
        return success_response(
            data=ExchangeRequestSerializer(exc).data,
            message=f"Exchange request {exc.exchange_number} created.",
            status_code=201,
        )


class AdminExchangeDetailView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def get(self, request, exc_id):
        exc = _get_exchange_or_404(exc_id, request.user)
        return success_response(data=ExchangeRequestSerializer(exc).data)

    def patch(self, request, exc_id):
        exc = _get_exchange_or_404(exc_id, request.user)
        s = UpdateExchangeSerializer(data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        exc = services.update_exchange_request(exc=exc, **s.validated_data)
        return success_response(data=ExchangeRequestSerializer(exc).data, message="Exchange updated.")

    def delete(self, request, exc_id):
        exc = _get_exchange_or_404(exc_id, request.user)
        services.delete_exchange_request(exc=exc)
        return success_response(message="Exchange deleted.")


class AdminExchangeApproveView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]
    def post(self, request, exc_id):
        exc = _get_exchange_or_404(exc_id, request.user)
        exc = services.approve_exchange(exc=exc, changed_by=request.user)
        return success_response(data=ExchangeRequestSerializer(exc).data, message="Exchange approved.")


class AdminExchangeRejectView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]
    def post(self, request, exc_id):
        exc = _get_exchange_or_404(exc_id, request.user)
        s   = RejectSerializer(data=request.data); s.is_valid(raise_exception=True)
        exc = services.reject_exchange(exc=exc, reason=s.validated_data["reason"], changed_by=request.user)
        return success_response(data=ExchangeRequestSerializer(exc).data, message="Exchange rejected.")


class AdminExchangeReceiveView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]
    def post(self, request, exc_id):
        exc = _get_exchange_or_404(exc_id, request.user)
        s   = MarkReceivedSerializer(data=request.data); s.is_valid(raise_exception=True)
        exc = services.mark_exchange_items_received(exc=exc, changed_by=request.user, **s.validated_data)
        return success_response(data=ExchangeRequestSerializer(exc).data, message="Items received.")


class AdminExchangeInspectView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]
    def post(self, request, exc_id):
        exc = _get_exchange_or_404(exc_id, request.user)
        s   = InspectItemsSerializer(data=request.data); s.is_valid(raise_exception=True)
        exc = services.inspect_exchange_items(exc=exc, changed_by=request.user, **s.validated_data)
        return success_response(data=ExchangeRequestSerializer(exc).data, message="Inspection complete.")


class AdminExchangeReintegrateView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]
    def post(self, request, exc_id):
        exc = _get_exchange_or_404(exc_id, request.user)
        exc = services.reintegrate_stock_for_exchange(exc=exc, changed_by=request.user)
        return success_response(data=ExchangeRequestSerializer(exc).data, message="Stock reintegrated.")


class AdminExchangeShipView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]
    def post(self, request, exc_id):
        exc = _get_exchange_or_404(exc_id, request.user)
        s   = ShipExchangeSerializer(data=request.data); s.is_valid(raise_exception=True)
        exc = services.ship_exchange(exc=exc, changed_by=request.user, **s.validated_data)
        return success_response(data=ExchangeRequestSerializer(exc).data, message="Exchange shipped.")


class AdminExchangeCompleteView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]
    def post(self, request, exc_id):
        exc = _get_exchange_or_404(exc_id, request.user)
        exc = services.complete_exchange(exc=exc, changed_by=request.user)
        return success_response(data=ExchangeRequestSerializer(exc).data, message="Exchange completed.")


# ─────────────────────────────────────────────────────────────
#  Return Policy
# ─────────────────────────────────────────────────────────────

class ReturnPolicyView(APIView):
    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated(), IsStaffOrAdmin()]

    def get(self, request):
        policy = services.get_active_policy()
        if not policy:
            return success_response(data=None, message="No return policy configured.")
        return success_response(data=ReturnPolicySerializer(policy).data)

    def patch(self, request):
        policy = ReturnPolicy.objects.filter(is_active=True).first()
        if not policy:
            policy = ReturnPolicy()
        s = ReturnPolicySerializer(policy, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        return success_response(data=s.data, message="Return policy updated.")
