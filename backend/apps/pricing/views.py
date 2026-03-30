from __future__ import annotations

from django.db.models import Q
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
        queryset = Coupon.objects.all().order_by("-created_at")
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
