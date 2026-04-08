from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import User, Address


# ─────────────────────────────────────────────────────────────
#  Registration
# ─────────────────────────────────────────────────────────────

class RegisterSerializer(serializers.Serializer):
    email      = serializers.EmailField()
    password   = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(max_length=150)
    last_name  = serializers.CharField(max_length=150)
    phone      = serializers.CharField(max_length=20, required=False, default="")
    turnstile_token = serializers.CharField(required=False, allow_blank=True, write_only=True)


# ─────────────────────────────────────────────────────────────
#  Login
# ─────────────────────────────────────────────────────────────

class LoginSerializer(serializers.Serializer):
    email    = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    turnstile_token = serializers.CharField(required=False, allow_blank=True, write_only=True)


# ─────────────────────────────────────────────────────────────
#  Token pair output
# ─────────────────────────────────────────────────────────────

class TokenPairSerializer(serializers.Serializer):
    access  = serializers.CharField(read_only=True)
    refresh = serializers.CharField(read_only=True)


# ─────────────────────────────────────────────────────────────
#  Password Reset
# ─────────────────────────────────────────────────────────────

class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    turnstile_token = serializers.CharField(required=False, allow_blank=True, write_only=True)


class PasswordResetConfirmSerializer(serializers.Serializer):
    token        = serializers.CharField()
    new_password = serializers.CharField(min_length=8, write_only=True)


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password     = serializers.CharField(min_length=8, write_only=True)


# ─────────────────────────────────────────────────────────────
#  User Profile
# ─────────────────────────────────────────────────────────────

class UserProfileSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model  = User
        fields = [
            "id", "email", "first_name", "last_name",
            "full_name", "phone", "role",
            "is_email_verified", "date_joined",
        ]
        read_only_fields = ["id", "email", "role", "date_joined", "is_email_verified"]

    def get_full_name(self, obj) -> str:
        return obj.full_name


class UpdateProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model  = User
        fields = ["first_name", "last_name", "phone"]


# ─────────────────────────────────────────────────────────────
#  Address
# ─────────────────────────────────────────────────────────────

class AddressSerializer(serializers.ModelSerializer):
    address_line1 = serializers.CharField(source="line1", required=False)
    address_line2 = serializers.CharField(source="line2", required=False, allow_blank=True)

    class Meta:
        model  = Address
        fields = [
            "id", "address_type", "is_default",
            "full_name", "line1", "line2", "address_line1", "address_line2",
            "city", "state", "postal_code", "country", "phone",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if self.instance is None and "line1" not in attrs:
            raise serializers.ValidationError({"line1": "Address line 1 is required."})
        return attrs


# ─────────────────────────────────────────────────────────────
#  Refresh (logout uses refresh token)
# ─────────────────────────────────────────────────────────────

class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


# ─────────────────────────────────────────────────────────────
#  Admin User Management
# ─────────────────────────────────────────────────────────────

class AdminCustomerSerializer(serializers.ModelSerializer):
    addresses = AddressSerializer(many=True, read_only=True)
    is_locked = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "email", "first_name", "last_name", "phone",
            "role", "is_active", "date_joined", "failed_login_attempts",
            "last_failed_login", "locked_until", "is_locked",
            "is_email_verified", "addresses"
        ]

    def get_is_locked(self, obj) -> bool:
        return bool(obj.is_locked)


class AdminCustomerCreateSerializer(serializers.Serializer):
    email      = serializers.EmailField()
    password   = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(max_length=150)
    last_name  = serializers.CharField(max_length=150, required=False, default="")
    phone      = serializers.CharField(max_length=20, required=False, default="")
    role       = serializers.CharField(max_length=20, required=False, default="customer")


class AdminCustomerUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "phone", "role", "is_active", "is_email_verified"]
