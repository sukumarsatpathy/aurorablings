from __future__ import annotations

from django.db.models import Q
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.permissions import IsStaffOrAdmin
from core.exceptions import NotFoundError
from core.response import success_response

from .models import Coupon
from .serializers import CouponSerializer


class CouponListView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def get(self, request):
        queryset = Coupon.objects.select_related("assigned_user").order_by("-created_at")

        # Personal gift coupons are excluded by default. There is one per
        # customer per occasion per year, so once the programme has been
        # running they outnumber the campaign coupons the admin screen is
        # actually for. `?assigned=true` brings them back when someone is
        # looking into a specific customer's gift.
        assigned = str(request.query_params.get("assigned", "")).strip().lower()
        if assigned in {"true", "1", "yes"}:
            queryset = queryset.filter(assigned_user__isnull=False)
        elif assigned not in {"all"}:
            queryset = queryset.filter(assigned_user__isnull=True)

        search = request.query_params.get("search")
        if search:
            queryset = queryset.filter(Q(code__icontains=search) | Q(type__icontains=search))

        is_active = request.query_params.get("is_active")
        if is_active is not None:
            normalized = str(is_active).strip().lower()
            if normalized in {"true", "1", "yes"}:
                queryset = queryset.filter(is_active=True)
            elif normalized in {"false", "0", "no"}:
                queryset = queryset.filter(is_active=False)

        return success_response(data=CouponSerializer(queryset, many=True).data)

    def post(self, request):
        serializer = CouponSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        coupon = serializer.save()
        return success_response(
            data=CouponSerializer(coupon).data,
            message="Coupon created.",
            status_code=201,
        )


class MyCouponsView(APIView):
    """
    The signed-in customer's own gift coupons.

    A gift the customer cannot find is not much of a gift: the email is the
    only place the code appears otherwise, and emails get deleted, filtered and
    lost. This returns live personal coupons only — never campaign coupons,
    which are not a per-customer thing, and never anyone else's.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        now = timezone.now()
        coupons = (
            Coupon.objects.filter(
                assigned_user=request.user,
                is_active=True,
                start_date__lte=now,
                end_date__gte=now,
            )
            .exclude(usages__user=request.user)
            .order_by("end_date")
        )
        return success_response(
            data=[
                {
                    "code": c.code,
                    "occasion": c.occasion,
                    "type": c.type,
                    "value": str(c.value),
                    "max_discount": str(c.max_discount) if c.max_discount is not None else None,
                    "min_order_value": str(c.min_order_value),
                    "expires_at": c.end_date.isoformat(),
                }
                for c in coupons
            ]
        )


class CouponDetailView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def _get_coupon(self, coupon_id):
        try:
            return Coupon.objects.get(id=coupon_id)
        except Coupon.DoesNotExist:
            raise NotFoundError("Coupon not found.")

    def get(self, request, coupon_id):
        coupon = self._get_coupon(coupon_id)
        return success_response(data=CouponSerializer(coupon).data)

    def patch(self, request, coupon_id):
        coupon = self._get_coupon(coupon_id)
        serializer = CouponSerializer(coupon, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        coupon = serializer.save()
        return success_response(
            data=CouponSerializer(coupon).data,
            message="Coupon updated.",
        )

    def delete(self, request, coupon_id):
        coupon = self._get_coupon(coupon_id)
        coupon.delete()
        return success_response(message="Coupon deleted.")
