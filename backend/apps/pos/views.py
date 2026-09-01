"""
pos.views
~~~~~~~~~

Staff-only endpoints for the counter.

Every one of these is behind ``IsStaffOrAdmin``. The counter tablet is not a
trusted device: it says how much cash it took and which order it took it for,
and the server decides everything else.
"""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsStaffOrAdmin
from apps.orders.models import Order
from apps.payments.tender_service import TenderError
from apps.pos import services
from apps.pos.models import POSShift, POSTerminal, ShiftStatus
from apps.pos.serializers import (
    CashMovementCreateSerializer,
    CashTenderSerializer,
    CloseShiftSerializer,
    OpenShiftSerializer,
    POSShiftSerializer,
    POSTerminalSerializer,
)


def _bad(message, code=status.HTTP_400_BAD_REQUEST):
    return Response({"detail": str(message)}, status=code)


class TerminalListView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def get(self, request):
        terminals = POSTerminal.objects.filter(is_active=True)
        return Response(POSTerminalSerializer(terminals, many=True).data)


class CurrentShiftView(APIView):
    """The open shift for a terminal, or for this staff member across terminals."""
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def get(self, request):
        shifts = POSShift.objects.filter(status=ShiftStatus.OPEN).select_related("terminal")
        terminal_id = request.query_params.get("terminal")
        if terminal_id:
            shifts = shifts.filter(terminal_id=terminal_id)
        shift = shifts.first()
        if not shift:
            return Response({"shift": None})
        return Response({"shift": POSShiftSerializer(shift).data})


class OpenShiftView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request):
        payload = OpenShiftSerializer(data=request.data)
        payload.is_valid(raise_exception=True)

        try:
            terminal = POSTerminal.objects.get(pk=payload.validated_data["terminal"], is_active=True)
        except POSTerminal.DoesNotExist:
            return _bad("Unknown or inactive terminal.", status.HTTP_404_NOT_FOUND)

        try:
            shift = services.open_shift(
                terminal=terminal,
                staff=request.user,
                opening_float=payload.validated_data["opening_float"],
            )
        except services.ShiftError as exc:
            return _bad(exc, status.HTTP_409_CONFLICT)

        return Response(POSShiftSerializer(shift).data, status=status.HTTP_201_CREATED)


class ShiftDetailView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def get(self, request, shift_id):
        try:
            shift = POSShift.objects.select_related("terminal").get(pk=shift_id)
        except POSShift.DoesNotExist:
            return _bad("Shift not found.", status.HTTP_404_NOT_FOUND)
        return Response(POSShiftSerializer(shift).data)


class CloseShiftView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request, shift_id):
        payload = CloseShiftSerializer(data=request.data)
        payload.is_valid(raise_exception=True)

        try:
            shift = POSShift.objects.select_related("terminal").get(pk=shift_id)
        except POSShift.DoesNotExist:
            return _bad("Shift not found.", status.HTTP_404_NOT_FOUND)

        try:
            shift = services.close_shift(
                shift=shift,
                staff=request.user,
                counted_cash=payload.validated_data["counted_cash"],
                note=payload.validated_data.get("note", ""),
                force=payload.validated_data["force"],
            )
        except services.ShiftError as exc:
            # 409, not 400: the request is well-formed, the drawer just isn't ready.
            return _bad(exc, status.HTTP_409_CONFLICT)

        return Response(POSShiftSerializer(shift).data)


class CashMovementView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request, shift_id):
        payload = CashMovementCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)

        try:
            shift = POSShift.objects.get(pk=shift_id)
        except POSShift.DoesNotExist:
            return _bad("Shift not found.", status.HTTP_404_NOT_FOUND)

        order = None
        if payload.validated_data.get("order"):
            order = Order.objects.filter(pk=payload.validated_data["order"]).first()

        try:
            movement = services.record_cash_movement(
                shift=shift,
                movement_type=payload.validated_data["movement_type"],
                amount=payload.validated_data["amount"],
                reason=payload.validated_data["reason"],
                staff=request.user,
                order=order,
            )
        except services.ShiftError as exc:
            return _bad(exc, status.HTTP_409_CONFLICT)

        return Response(
            {"id": str(movement.id), "expected_cash_now": str(services.expected_cash(shift))},
            status=status.HTTP_201_CREATED,
        )


class CashTenderView(APIView):
    """Take cash for one leg of a sale."""
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request, shift_id):
        payload = CashTenderSerializer(data=request.data)
        payload.is_valid(raise_exception=True)

        try:
            shift = POSShift.objects.get(pk=shift_id)
        except POSShift.DoesNotExist:
            return _bad("Shift not found.", status.HTTP_404_NOT_FOUND)

        try:
            order = Order.objects.get(pk=payload.validated_data["order"])
        except Order.DoesNotExist:
            return _bad("Order not found.", status.HTTP_404_NOT_FOUND)

        try:
            tender = services.take_cash_tender(
                order=order,
                shift=shift,
                staff=request.user,
                amount_applied=payload.validated_data["amount_applied"],
                cash_received=payload.validated_data.get("cash_received"),
            )
        except (services.ShiftError, TenderError) as exc:
            return _bad(exc, status.HTTP_409_CONFLICT)

        order.refresh_from_db()
        from apps.payments import tender_service

        return Response(
            {
                "tender_id": str(tender.id),
                "amount_applied": str(tender.amount_applied),
                "cash_received": str(tender.cash_received),
                "change_given": str(tender.change_given),
                "order_payment_status": order.payment_status,
                "balance_due": str(tender_service.balance_due(order)),
                "expected_cash_now": str(services.expected_cash(shift)),
            },
            status=status.HTTP_201_CREATED,
        )
