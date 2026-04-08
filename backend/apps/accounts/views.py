"""
accounts.views
~~~~~~~~~~~~~~
Thin views — validate input via serializers, delegate to services,
return standard Aurora envelope responses.

Rate limiting is applied via the @ratelimit decorator (django-ratelimit).
Key = client IP.  Burst: 10 req/min per endpoint.
"""
from __future__ import annotations

from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView

from core.response import success_response, error_response
from core.logging import get_logger
from core.turnstile import verify_turnstile_token, get_client_ip

from . import services, selectors
from .models import Address
from .serializers import (
    RegisterSerializer,
    LoginSerializer,
    LogoutSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
    ChangePasswordSerializer,
    UserProfileSerializer,
    UpdateProfileSerializer,
    AddressSerializer,
    AdminCustomerSerializer,
    AdminCustomerCreateSerializer,
    AdminCustomerUpdateSerializer,
)
from .permissions import IsOwnerOrAdmin, IsStaffOrAdmin

logger = get_logger(__name__)

_RL_LOGIN = {"key": "ip", "rate": "10/m", "block": False}
_RL_REGISTER = {"key": "ip", "rate": "8/m", "block": False}
_RL_FORGOT = {"key": "ip", "rate": "8/m", "block": False}


# ─────────────────────────────────────────────────────────
#  Registration
# ─────────────────────────────────────────────────────────

class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "auth_register"

    @method_decorator(ratelimit(**_RL_REGISTER))
    def post(self, request):
        limited_response = _rate_limit_error_if_limited(request, endpoint="auth.register")
        if limited_response is not None:
            return limited_response

        s = RegisterSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        payload = dict(s.validated_data)
        token = payload.pop("turnstile_token", "")
        if not verify_turnstile_token(token=token, remote_ip=get_client_ip(request), action="auth.register"):
            return error_response(
                message="CAPTCHA verification failed.",
                error_code="turnstile_verification_failed",
                errors={"turnstile_token": ["Invalid or missing CAPTCHA token."]},
                status_code=status.HTTP_400_BAD_REQUEST,
                request_id=getattr(request, "request_id", None),
            )

        user = services.register_user(**payload)
        tokens = services.issue_auth_tokens(user=user)

        # Fire welcome email async
        from .tasks import send_welcome_email
        send_welcome_email.delay(user_id=str(user.id))

        return success_response(
            data={
                "access": tokens["access"],
                "refresh": tokens["refresh"],
                "user": UserProfileSerializer(user).data,
            },
            message="Account created successfully.",
            status_code=status.HTTP_201_CREATED,
            request_id=getattr(request, "request_id", None),
        )


# ─────────────────────────────────────────────────────────
#  Login
# ─────────────────────────────────────────────────────────

class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "auth_login"

    @method_decorator(ratelimit(**_RL_LOGIN))
    def post(self, request):
        limited_response = _rate_limit_error_if_limited(request, endpoint="auth.login")
        if limited_response is not None:
            return limited_response

        s = LoginSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        token = s.validated_data.get("turnstile_token", "")
        if not verify_turnstile_token(token=token, remote_ip=get_client_ip(request), action="auth.login"):
            return error_response(
                message="CAPTCHA verification failed.",
                error_code="turnstile_verification_failed",
                errors={"turnstile_token": ["Invalid or missing CAPTCHA token."]},
                status_code=status.HTTP_400_BAD_REQUEST,
                request_id=getattr(request, "request_id", None),
            )

        result = services.login_user(
            email=s.validated_data["email"],
            password=s.validated_data["password"],
            ip_address=get_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
            request=request,
        )

        return success_response(
            data={
                "access":  result["access"],
                "refresh": result["refresh"],
                "user":    UserProfileSerializer(result["user"]).data,
            },
            message="Login successful.",
            request_id=getattr(request, "request_id", None),
        )


# ─────────────────────────────────────────────────────────
#  Logout
# ─────────────────────────────────────────────────────────

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        s = LogoutSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        services.logout_user(s.validated_data["refresh"], request=request, user=request.user)
        return success_response(
            message="Logged out successfully.",
            request_id=getattr(request, "request_id", None),
        )


# ─────────────────────────────────────────────────────────
#  Password Reset
# ─────────────────────────────────────────────────────────

class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "auth_forgot_password"

    @method_decorator(ratelimit(**_RL_FORGOT))
    def post(self, request):
        limited_response = _rate_limit_error_if_limited(request, endpoint="auth.password_reset_request")
        if limited_response is not None:
            return limited_response

        s = PasswordResetRequestSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        token = s.validated_data.get("turnstile_token", "")
        if not verify_turnstile_token(token=token, remote_ip=get_client_ip(request), action="auth.password_reset_request"):
            return error_response(
                message="CAPTCHA verification failed.",
                error_code="turnstile_verification_failed",
                errors={"turnstile_token": ["Invalid or missing CAPTCHA token."]},
                status_code=status.HTTP_400_BAD_REQUEST,
                request_id=getattr(request, "request_id", None),
            )

        services.initiate_password_reset(email=s.validated_data["email"])
        # Always return 200 — prevent email enumeration
        return success_response(
            message="If an account with that email exists, a reset link has been sent.",
            request_id=getattr(request, "request_id", None),
        )


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        s = PasswordResetConfirmSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        services.confirm_password_reset(
            token=s.validated_data["token"],
            new_password=s.validated_data["new_password"],
        )
        return success_response(
            message="Password reset successfully. You can now log in.",
            request_id=getattr(request, "request_id", None),
        )


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        s = ChangePasswordSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        user = request.user
        if not user.check_password(s.validated_data["current_password"]):
            return error_response(
                message="Current password is incorrect.",
                error_code="wrong_password",
                status_code=status.HTTP_400_BAD_REQUEST,
                request_id=getattr(request, "request_id", None),
            )

        from core.exceptions import ValidationError
        services._validate_password_strength(s.validated_data["new_password"])
        user.set_password(s.validated_data["new_password"])
        user.save(update_fields=["password"])
        logger.info("password_changed", user_id=str(user.id))

        return success_response(
            message="Password changed successfully.",
            request_id=getattr(request, "request_id", None),
        )


# ─────────────────────────────────────────────────────────
#  Profile
# ─────────────────────────────────────────────────────────

class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return success_response(
            data=UserProfileSerializer(request.user).data,
            request_id=getattr(request, "request_id", None),
        )

    def patch(self, request):
        s = UpdateProfileSerializer(request.user, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        logger.info("profile_updated", user_id=str(request.user.id))
        return success_response(
            data=UserProfileSerializer(request.user).data,
            message="Profile updated.",
            request_id=getattr(request, "request_id", None),
        )


# ─────────────────────────────────────────────────────────
#  Addresses
# ─────────────────────────────────────────────────────────

class AddressListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        addresses = selectors.get_addresses_for_user(request.user)
        return success_response(
            data=AddressSerializer(addresses, many=True).data,
            request_id=getattr(request, "request_id", None),
        )

    def post(self, request):
        s = AddressSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        address = services.create_address(user=request.user, data=s.validated_data)
        return success_response(
            data=AddressSerializer(address).data,
            message="Address added.",
            status_code=status.HTTP_201_CREATED,
            request_id=getattr(request, "request_id", None),
        )


class AddressDetailView(APIView):
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]

    def _get_address(self, request, pk):
        from core.exceptions import NotFoundError
        address = selectors.get_address_by_id(pk, request.user)
        if not address:
            raise NotFoundError("Address not found.")
        self.check_object_permissions(request, address)
        return address

    def get(self, request, pk):
        address = self._get_address(request, pk)
        return success_response(
            data=AddressSerializer(address).data,
            request_id=getattr(request, "request_id", None),
        )

    def patch(self, request, pk):
        address = self._get_address(request, pk)
        s = AddressSerializer(address, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        address = services.update_address(address=address, data=s.validated_data, changed_by=request.user)
        return success_response(
            data=AddressSerializer(address).data,
            message="Address updated.",
            request_id=getattr(request, "request_id", None),
        )

    def delete(self, request, pk):
        address = self._get_address(request, pk)
        services.delete_address(address=address)
        return success_response(
            message="Address deleted.",
            request_id=getattr(request, "request_id", None),
        )


# ─────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────

def _rate_limit_error_if_limited(request, *, endpoint: str):
    if not getattr(request, "limited", False):
        return None
    logger.warning(
        "rate_limit_blocked",
        endpoint=endpoint,
        remote_ip=get_client_ip(request),
        user_id=str(getattr(getattr(request, "user", None), "id", "") or ""),
    )
    return error_response(
        message="Too many requests. Please try again later.",
        error_code="rate_limited",
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        request_id=getattr(request, "request_id", None),
    )


# ─────────────────────────────────────────────────────────
#  Admin Customers
# ─────────────────────────────────────────────────────────

class AdminCustomerListView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def get(self, request):
        users = selectors.get_all_users()
        # Optional: filtering via query params
        search = request.query_params.get("search")
        if search:
            from django.db.models import Q
            users = users.filter(
                Q(email__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search)
            )
        role = request.query_params.get("role")
        if role:
            users = users.filter(role=role)

        data = AdminCustomerSerializer(users, many=True).data
        return success_response(
            data=data,
            request_id=getattr(request, "request_id", None),
        )

    def post(self, request):
        s = AdminCustomerCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        
        user = services.register_user(**s.validated_data)
        
        return success_response(
            data=AdminCustomerSerializer(user).data,
            message="User created successfully.",
            status_code=status.HTTP_201_CREATED,
            request_id=getattr(request, "request_id", None),
        )


class AdminCustomerDetailView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def _get_user(self, pk):
        from core.exceptions import NotFoundError
        user = selectors.get_user_by_id(pk)
        if not user:
            raise NotFoundError("User not found.")
        return user

    def get(self, request, pk):
        user = self._get_user(pk)
        return success_response(
            data=AdminCustomerSerializer(user).data,
            request_id=getattr(request, "request_id", None),
        )

    def patch(self, request, pk):
        user = self._get_user(pk)
        s = AdminCustomerUpdateSerializer(user, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        logger.info("admin_updated_user", admin_id=str(request.user.id), target_user_id=str(user.id))
        return success_response(
            data=AdminCustomerSerializer(user).data,
            message="User updated successfully.",
            request_id=getattr(request, "request_id", None),
        )

    def delete(self, request, pk):
        user = self._get_user(pk)
        # Soft delete
        user.is_active = False
        user.save(update_fields=["is_active"])
        logger.info("admin_deleted_user", admin_id=str(request.user.id), target_user_id=str(user.id))
        return success_response(
            message="User deactivated successfully.",
            request_id=getattr(request, "request_id", None),
        )


class AdminCustomerSendWelcomeEmailView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request, pk):
        from core.exceptions import NotFoundError
        from apps.notifications.email_service import send_welcome_email as send_welcome_email_now
        from apps.notifications.models import EmailLog

        user = selectors.get_user_by_id(pk)
        if not user:
            raise NotFoundError("User not found.")

        if not user.email:
            return error_response(
                message="User does not have a valid email address.",
                error_code="missing_email",
                status_code=status.HTTP_400_BAD_REQUEST,
                request_id=getattr(request, "request_id", None),
            )

        sent = send_welcome_email_now(user)
        if not sent:
            latest_failure = (
                EmailLog.objects.filter(recipient=user.email, status=EmailLog.STATUS_FAILED)
                .order_by("-created_at")
                .first()
            )
            detail = (
                latest_failure.error_message
                if latest_failure and latest_failure.error_message
                else "Unknown provider error. Please verify Notification Delivery and Brevo/SMTP settings."
            )
            return error_response(
                message="Welcome email failed to send. Please verify SMTP/Brevo settings.",
                error_code="email_send_failed",
                errors={"detail": detail},
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                request_id=getattr(request, "request_id", None),
            )

        logger.info("admin_triggered_welcome_email", admin_id=str(request.user.id), target_user_id=str(user.id), mode="sync")
        return success_response(
            message="Welcome email sent successfully.",
            data={"user_id": str(user.id), "email": user.email},
            request_id=getattr(request, "request_id", None),
        )


class AdminCustomerUnblockView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request, pk):
        from core.exceptions import NotFoundError

        user = selectors.get_user_by_id(pk)
        if not user:
            raise NotFoundError("User not found.")

        services.unlock_user_account(user=user, changed_by=request.user, request=request)
        return success_response(
            message="Customer account unlocked successfully.",
            data=AdminCustomerSerializer(user).data,
            request_id=getattr(request, "request_id", None),
        )


# ─────────────────────────────────────────────────────────
#  Admin Addresses
# ─────────────────────────────────────────────────────────

class AdminAddressListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def get(self, request, user_id):
        user = selectors.get_user_by_id(user_id)
        if not user:
            from core.exceptions import NotFoundError
            raise NotFoundError("User not found.")
        addresses = selectors.get_addresses_for_user(user)
        return success_response(
            data=AddressSerializer(addresses, many=True).data,
            request_id=getattr(request, "request_id", None),
        )

    def post(self, request, user_id):
        user = selectors.get_user_by_id(user_id)
        if not user:
            from core.exceptions import NotFoundError
            raise NotFoundError("User not found.")
        s = AddressSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        address = services.create_address(user=user, data=s.validated_data)
        return success_response(
            data=AddressSerializer(address).data,
            message="Address added.",
            status_code=status.HTTP_201_CREATED,
            request_id=getattr(request, "request_id", None),
        )


class AdminAddressDetailView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def _get_address(self, user_id, pk):
        from core.exceptions import NotFoundError
        # Use our own selector or filter directly
        try:
            return Address.objects.get(id=pk, user_id=user_id)
        except Address.DoesNotExist:
            raise NotFoundError("Address not found.")

    def patch(self, request, user_id, pk):
        address = self._get_address(user_id, pk)
        s = AddressSerializer(address, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        address = services.update_address(address=address, data=s.validated_data, changed_by=request.user)
        return success_response(
            data=AddressSerializer(address).data,
            message="Address updated.",
            request_id=getattr(request, "request_id", None),
        )

    def delete(self, request, user_id, pk):
        address = self._get_address(user_id, pk)
        services.delete_address(address=address)
        return success_response(
            message="Address deleted.",
            request_id=getattr(request, "request_id", None),
        )
