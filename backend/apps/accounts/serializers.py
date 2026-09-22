from datetime import date

from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import User, Address


# ─────────────────────────────────────────────────────────────
#  Occasion dates (birthday / anniversary)
# ─────────────────────────────────────────────────────────────

# Anyone claiming to be older than this mistyped the year.
MAX_AGE_YEARS = 120
# A reward programme aimed at children is not something we want to run by
# accident, and a birthday field is the one place a child's age enters the
# system. Under-13s are refused the field rather than silently enrolled.
MIN_AGE_YEARS = 13


class OccasionDateValidationMixin:
    """
    Shared validation for ``date_of_birth`` and ``anniversary_date``.

    Mixed into every serializer that can write them — customer profile, admin
    edit, POS — so the rules cannot drift between the three surfaces. A date
    that fails here never reaches the database, which matters because the
    occasion sweep trusts what it reads.
    """

    def validate_date_of_birth(self, value):
        if value is None:
            return value
        today = date.today()
        if value > today:
            raise serializers.ValidationError("Date of birth cannot be in the future.")
        age = (today - value).days / 365.2425
        if age > MAX_AGE_YEARS:
            raise serializers.ValidationError("Please check the year — that date is not plausible.")
        if age < MIN_AGE_YEARS:
            raise serializers.ValidationError(
                f"You must be at least {MIN_AGE_YEARS} to add a birthday."
            )
        return value

    def validate_anniversary_date(self, value):
        if value is None:
            return value
        today = date.today()
        if value > today:
            raise serializers.ValidationError("Anniversary date cannot be in the future.")
        if (today - value).days / 365.2425 > MAX_AGE_YEARS:
            raise serializers.ValidationError("Please check the year — that date is not plausible.")
        return value


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
            "date_of_birth", "anniversary_date",
            "is_email_verified", "date_joined",
        ]
        read_only_fields = ["id", "email", "role", "date_joined", "is_email_verified"]

    def get_full_name(self, obj) -> str:
        return obj.full_name


class UpdateProfileSerializer(OccasionDateValidationMixin, serializers.ModelSerializer):
    # allow_null so a customer can clear a date they no longer want us to have.
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    anniversary_date = serializers.DateField(required=False, allow_null=True)

    class Meta:
        model  = User
        fields = ["first_name", "last_name", "phone", "date_of_birth", "anniversary_date"]


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
            "date_of_birth", "anniversary_date",
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


class AdminCustomerUpdateSerializer(OccasionDateValidationMixin, serializers.ModelSerializer):
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    anniversary_date = serializers.DateField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = [
            "first_name", "last_name", "phone",
            "date_of_birth", "anniversary_date",
            "role", "is_active", "is_email_verified",
        ]
