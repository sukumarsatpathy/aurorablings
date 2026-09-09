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
    ManualDiscountSerializer,
    POSOrderCreateSerializer,
    POSQuoteSerializer,
    VoidSaleSerializer,
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


class PartPaidOrderListView(APIView):
    """
    Sales holding cash that were never completed.

    Belongs on the counter screen permanently, not behind a menu — this is the
    list that stops a shift closing on money nobody can account for.
    """
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def get(self, request):
        from apps.payments import tender_service

        orders = services.part_paid_orders(
            terminal=request.query_params.get("terminal") or None,
            shift=request.query_params.get("shift") or None,
        )
        return Response([
            {
                "id": str(o.id),
                "order_number": o.order_number,
                "grand_total": str(o.grand_total),
                "amount_paid": str(tender_service.amount_paid(o)),
                "balance_due": str(tender_service.balance_due(o)),
                "terminal": o.pos_terminal.code if o.pos_terminal else None,
                "contact_name": o.contact_name,
                "contact_phone": o.contact_phone,
                "created_at": o.created_at,
            }
            for o in orders
        ])


class VoidSaleView(APIView):
    """Abandon a part-paid sale and take the cash back out of the drawer."""
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request, order_id):
        payload = VoidSaleSerializer(data=request.data)
        payload.is_valid(raise_exception=True)

        try:
            order = Order.objects.get(pk=order_id)
        except Order.DoesNotExist:
            return _bad("Order not found.", status.HTTP_404_NOT_FOUND)

        try:
            order = services.void_sale(
                order=order, staff=request.user, reason=payload.validated_data["reason"],
            )
        except services.ShiftError as exc:
            return _bad(exc, status.HTTP_409_CONFLICT)
        except Exception as exc:  # ConflictError from the order state machine
            return _bad(exc, status.HTTP_409_CONFLICT)

        return Response({
            "order_number": order.order_number,
            "status": order.status,
            "payment_status": order.payment_status,
        })


class UpiCollectionView(APIView):
    """
    Raise a dynamic QR for the outstanding balance on a sale.

    The request body carries no amount. On a split sale the customer has already
    paid part in cash, and a QR for the total would charge them twice — so the
    amount comes from the ledger, here, on the server.
    """
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request, order_id):
        from apps.pos import collection_service

        try:
            order = Order.objects.get(pk=order_id)
        except Order.DoesNotExist:
            return _bad("Order not found.", status.HTTP_404_NOT_FOUND)

        # Regenerating: close the old QR first, so an expired code and its
        # replacement can never both be paid.
        previous = request.data.get("replaces")
        if previous:
            collection_service.cancel_collection(transaction_id=previous)

        shift = None
        if request.data.get("shift"):
            shift = POSShift.objects.filter(pk=request.data["shift"], status=ShiftStatus.OPEN).first()

        try:
            payload = collection_service.create_upi_collection(
                order=order, staff=request.user, shift=shift,
            )
        except collection_service.CollectionError as exc:
            return _bad(exc, status.HTTP_409_CONFLICT)

        return Response(payload, status=status.HTTP_201_CREATED)


class PaymentStateView(APIView):
    """
    What the counter polls while the customer is scanning.

    Reads the tender ledger. It deliberately does not ask Razorpay whether the
    customer paid — only a signature-verified webhook may turn this till green.
    """
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def get(self, request, order_id):
        from apps.pos import collection_service

        try:
            order = Order.objects.get(pk=order_id)
        except Order.DoesNotExist:
            return _bad("Order not found.", status.HTTP_404_NOT_FOUND)

        return Response(collection_service.payment_state(order=order))


class ShiftSummaryView(APIView):
    """The close-out figures: what was traded, by tender, and what the drawer owes."""
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def get(self, request, shift_id):
        try:
            shift = POSShift.objects.select_related("terminal").get(pk=shift_id)
        except POSShift.DoesNotExist:
            return _bad("Shift not found.", status.HTTP_404_NOT_FOUND)
        return Response(services.shift_summary(shift))


class ShiftHistoryView(APIView):
    """Recent shifts, newest first. Filterable by terminal."""
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def get(self, request):
        shifts = POSShift.objects.select_related("terminal").order_by("-opened_at")
        if request.query_params.get("terminal"):
            shifts = shifts.filter(terminal_id=request.query_params["terminal"])
        if request.query_params.get("status"):
            shifts = shifts.filter(status=request.query_params["status"])

        try:
            limit = min(int(request.query_params.get("limit", 30)), 100)
        except (TypeError, ValueError):
            limit = 30

        return Response(POSShiftSerializer(shifts[:limit], many=True).data)


class POSQuoteView(APIView):
    """Price a cart without creating anything."""
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request):
        from apps.pos import order_service

        payload = POSQuoteSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        items = [
            {"variant_id": str(i["variant_id"]), "quantity": i["quantity"]}
            for i in payload.validated_data["items"]
        ]
        try:
            return Response(order_service.quote(
                items=items,
                coupon_code=payload.validated_data.get("coupon_code", ""),
                fulfilment_type=payload.validated_data["fulfilment_type"],
            ))
        except Exception as exc:  # pricing/stock validation errors
            return _bad(exc)


class POSOrderCreateView(APIView):
    """Ring up a sale. Unpaid on creation — money is taken separately."""
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request):
        from apps.pos import order_service

        payload = POSOrderCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data

        shift = POSShift.objects.filter(pk=data["shift"], status=ShiftStatus.OPEN).first()
        if shift is None:
            return _bad("No open shift with that id.", status.HTTP_409_CONFLICT)

        items = [
            {"variant_id": str(i["variant_id"]), "quantity": i["quantity"]}
            for i in data["items"]
        ]
        try:
            order = order_service.create_pos_order(
                items=items,
                shift=shift,
                staff=request.user,
                contact_name=data.get("contact_name", ""),
                contact_phone=data.get("contact_phone", ""),
                contact_email=data.get("contact_email", ""),
                create_account=data.get("create_account", True),
                coupon_code=data.get("coupon_code", ""),
                fulfilment_type=data["fulfilment_type"],
                shipping_address=data.get("shipping_address"),
                notes=data.get("notes", ""),
            )
        except order_service.POSOrderError as exc:
            return _bad(exc, status.HTTP_409_CONFLICT)
        except Exception as exc:  # stock/pricing failures from place_order
            return _bad(exc)

        return Response({
            "order_id": str(order.id),
            "order_number": order.order_number,
            "subtotal": str(order.subtotal),
            "discount_amount": str(order.discount_amount),
            "grand_total": str(order.grand_total),
            "fulfilment_type": order.fulfilment_type,
        }, status=status.HTTP_201_CREATED)


class ManualDiscountView(APIView):
    """
    Apply a staff discount.

    The ceiling is enforced in the service, not here and not in the tablet — a
    counter device is shared and unlocked, and this is the copy that counts.
    """
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request, order_id):
        from apps.pos import order_service

        payload = ManualDiscountSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data

        try:
            order = Order.objects.get(pk=order_id)
        except Order.DoesNotExist:
            return _bad("Order not found.", status.HTTP_404_NOT_FOUND)

        approver = None
        if data.get("approver_email") and data.get("approver_password"):
            approver = order_service.authenticate_approver(
                email=data["approver_email"], password=data["approver_password"],
            )
            if approver is None:
                return _bad("Manager approval failed.", status.HTTP_403_FORBIDDEN)

        try:
            order = order_service.apply_manual_discount(
                order=order,
                percent=data.get("percent"),
                amount=data.get("amount"),
                reason=data["reason"],
                staff=request.user,
                approved_by=approver,
            )
        except order_service.POSOrderError as exc:
            return _bad(exc, status.HTTP_409_CONFLICT)

        return Response({
            "order_number": order.order_number,
            "manual_discount_amount": str(order.manual_discount_amount),
            "reason": order.manual_discount_reason,
            "approved": approver is not None,
            "grand_total": str(order.grand_total),
        })


def _available(variant) -> int:
    """
    Sellable units for a variant, matching ProductVariant.available_quantity.

    Warehouse rows win when any exist; the legacy `stock_quantity` column is the
    fallback for variants inventory has never touched. Reads the annotations set
    by CatalogueSearchView when present so a page of results is one query.
    """
    rows = getattr(variant, "wh_rows", None)
    if rows is None:
        return int(variant.available_quantity)
    if int(rows or 0) > 0:
        return int(getattr(variant, "wh_available", 0) or 0)
    return int(variant.stock_quantity or 0)


class CatalogueSearchView(APIView):
    """
    Variant-level search for the counter.

    The catalogue API searches products; a till needs the thing with a price and
    a stock count on it, which is the variant. Flat rows, one query, capped —
    a stall on 4G types a couple of characters and expects results, not a tree
    to expand.
    """
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def get(self, request):
        from django.db.models import Count, Prefetch, Q, Sum

        from apps.catalog.models import ProductMedia, ProductVariant

        query = (request.query_params.get("q") or "").strip()
        # Stock has two possible homes: WarehouseStock rows in the inventory app,
        # and the legacy `stock_quantity` column on the variant. The storefront
        # reads ProductVariant.available_quantity, which prefers the warehouse
        # rows and only falls back to the column. The till must use the same
        # source or it will call a fully stocked variant out of stock — the
        # column is a placeholder that stays at 0 once inventory is in use.
        # Annotated rather than read per row: a search returns up to 100 variants
        # and the property costs a query each.
        _active_wh = Q(stock_records__warehouse__is_active=True)
        variants = (
            ProductVariant.objects
            .filter(is_active=True, product__is_active=True)
            .select_related("product")
            # One image per row, fetched in one extra query rather than one per
            # variant. Ordered so the flagged primary wins; the till only ever
            # renders the first.
            .prefetch_related(
                Prefetch(
                    "product__media",
                    queryset=ProductMedia.objects.order_by("-is_primary", "sort_order"),
                    to_attr="pos_media",
                )
            )
            .annotate(
                wh_available=Sum("stock_records__available", filter=_active_wh),
                wh_rows=Count("stock_records", filter=_active_wh),
            )
        )

        # Restoring a cart after a refresh: the till knows which variants it had,
        # and needs today's price and stock for each rather than whatever it
        # remembered. Prices and stock are re-read here, never restored from the
        # browser.
        ids = [i for i in (request.query_params.get("ids") or "").split(",") if i.strip()]
        if ids:
            return Response(self._rows(variants.filter(id__in=ids[:100])))

        if query:
            variants = variants.filter(
                Q(sku__icontains=query)
                | Q(name__icontains=query)
                | Q(product__name__icontains=query)
            )

        try:
            limit = min(int(request.query_params.get("limit", 40)), 100)
        except (TypeError, ValueError):
            limit = 40

        return Response(self._rows(variants.order_by("product__name", "name")[:limit]))

    @staticmethod
    def _thumbnail(variant, request):
        """
        The product's primary image, at the smallest generated size.

        Images live on the product, not the variant, so every variant of a
        product shows the same picture — which is what a staff member needs:
        they are looking for "the green jhumkas", then picking the size. The
        small derivative is deliberate: a stall runs on 4G and a grid of
        full-size jewellery photographs is a counter that will not load.
        """
        from core.media import build_media_url

        media = getattr(variant.product, "pos_media", None) if variant.product_id else None
        if not media:
            return None
        first = media[0]
        return build_media_url(first.image_small or first.image, request=request)

    def _rows(self, variants):
        request = self.request
        return [
            {
                "variant_id": str(v.id),
                "sku": v.sku,
                "product_name": v.product.name if v.product_id else "",
                "variant_name": v.name or "",
                "price": str(v.effective_price),
                "compare_at_price": str(v.compare_at_price) if v.compare_at_price else None,
                "stock": _available(v),
                "track_inventory": v.track_inventory,
                "low_stock": _available(v) <= v.low_stock_threshold,
                "image": self._thumbnail(v, request),
            }
            for v in variants
        ]


class CustomerLookupView(APIView):
    """
    Is this number already a customer?

    Phone is the identity at a counter, so this is the first thing staff do. It
    returns only what a staff member needs to greet someone correctly — name,
    whether an account exists, and how many past orders. Not an address book:
    anything more would make the till a customer-data export.
    """
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def get(self, request):
        from apps.accounts.customer_linking import find_customer, phone_digits
        from apps.orders.models import Order

        phone = (request.query_params.get("phone") or "").strip()
        if len(phone_digits(phone)) < 10:
            return _bad("Enter a full phone number.")

        match = find_customer(phone=phone, email=(request.query_params.get("email") or "").strip())

        if match.conflict and match.user is None:
            return Response({
                "found": False,
                "conflict": True,
                "reason": match.reason,
            })

        if match.user is None:
            return Response({"found": False, "conflict": False, "reason": match.reason})

        user = match.user
        return Response({
            "found": True,
            "conflict": match.conflict,
            "reason": match.reason,
            "customer": {
                "id": str(user.id),
                "name": user.get_full_name() or user.email,
                "email": user.email,
                "phone": user.phone,
                "orders": Order.objects.filter(user=user).count(),
            },
        })
