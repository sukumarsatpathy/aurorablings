from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from core.response import error_response, success_response

from .serializers import CookieConsentCurrentSerializer, CookieConsentSerializer
from .services import get_current_consent, save_consent, withdraw_consent


class CookieConsentCreateView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = CookieConsentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        log = save_consent(serializer.validated_data, request)

        return success_response(
            data={
                "id": log.id,
                "anonymous_id": log.anonymous_id,
                "created_at": log.created_at,
            },
            message="Cookie consent logged successfully.",
            request_id=getattr(request, "request_id", None),
        )


class CookieConsentWithdrawView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        anonymous_id = str(request.data.get("anonymous_id", "")).strip() or None
        log = withdraw_consent(request, anonymous_id=anonymous_id)

        return success_response(
            data={
                "id": log.id,
                "anonymous_id": log.anonymous_id,
                "status": log.consent_status,
                "created_at": log.created_at,
            },
            message="Cookie consent withdrawn successfully.",
            request_id=getattr(request, "request_id", None),
        )


class CookieConsentCurrentView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        anonymous_id = str(request.query_params.get("anonymous_id", "")).strip() or None

        if not (request.user and request.user.is_authenticated) and not anonymous_id:
            return error_response(
                message="Provide anonymous_id for anonymous users.",
                error_code="missing_anonymous_id",
                status_code=400,
                request_id=getattr(request, "request_id", None),
            )

        log = get_current_consent(request=request, anonymous_id=anonymous_id)
        if not log:
            return success_response(data=None, message="No consent log found.", request_id=getattr(request, "request_id", None))

        payload = CookieConsentCurrentSerializer(log).data
        return success_response(data=payload, request_id=getattr(request, "request_id", None))
