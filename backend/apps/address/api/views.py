from __future__ import annotations

from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from core.exceptions import ValidationError
from core.logging import get_logger
from core.response import error_response, success_response

from apps.address.selectors.address_selector import lookup_by_coordinates, lookup_by_pincode

logger = get_logger(__name__)

_RL_PUBLIC = {"key": "ip", "rate": "50/m", "block": True}


class ReverseLookupSerializer(serializers.Serializer):
    lat = serializers.FloatField()
    lng = serializers.FloatField()


class PincodeLookupView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @method_decorator(ratelimit(**_RL_PUBLIC))
    def get(self, request, pincode: str):
        request_id = getattr(request, "request_id", None)
        try:
            payload = lookup_by_pincode(pincode)
            return success_response(
                data=payload,
                request_id=request_id,
            )
        except ValidationError as exc:
            return error_response(
                message=exc.message,
                error_code=exc.code,
                errors=exc.extra,
                status_code=exc.status_code,
                request_id=request_id,
            )
        except Exception as exc:
            logger.warning("pincode_lookup_view_failed", pincode=pincode, error=str(exc))
            return success_response(
                data={"city": "", "state": "", "area": "", "areas": [], "pincode": ""},
                message="Address auto-detection unavailable. Manual entry is allowed.",
                request_id=request_id,
            )


class ReverseLookupView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @method_decorator(ratelimit(**_RL_PUBLIC))
    def post(self, request):
        request_id = getattr(request, "request_id", None)
        serializer = ReverseLookupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            payload = lookup_by_coordinates(
                lat=serializer.validated_data["lat"],
                lng=serializer.validated_data["lng"],
            )
            return success_response(
                data=payload,
                request_id=request_id,
            )
        except ValidationError as exc:
            return error_response(
                message=exc.message,
                error_code=exc.code,
                errors=exc.extra,
                status_code=exc.status_code,
                request_id=request_id,
            )
        except Exception as exc:
            logger.warning("reverse_lookup_view_failed", error=str(exc))
            return success_response(
                data={"city": "", "state": "", "area": "", "areas": [], "pincode": ""},
                message="Reverse lookup unavailable. Manual entry is allowed.",
                request_id=request_id,
            )
