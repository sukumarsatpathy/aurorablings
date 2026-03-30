"""
accounts.permissions
~~~~~~~~~~~~~~~~~~~~
Custom DRF permission classes.

Usage in viewsets:
    permission_classes = [IsAuthenticated, IsAdminUser]
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
"""
from rest_framework.permissions import BasePermission, SAFE_METHODS
from .models import UserRole


class IsAdminUser(BasePermission):
    """Allow access only to users with role=admin."""
    message = "This action requires Admin privileges."

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role == UserRole.ADMIN
        )


class IsStaffOrAdmin(BasePermission):
    """Allow access to staff and admin users."""
    message = "This action requires Staff or Admin privileges."

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role in (UserRole.STAFF, UserRole.ADMIN)
        )


class IsCustomer(BasePermission):
    """Allow access only to customers."""
    message = "This action is for customers only."

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role == UserRole.CUSTOMER
        )


class IsOwnerOrAdmin(BasePermission):
    """
    Object-level permission.
    Allow if the user owns the object OR is an admin.

    The object must have a `user` FK attribute.
    """
    message = "You do not have permission to access this resource."

    def has_object_permission(self, request, view, obj):
        if request.user.role == UserRole.ADMIN:
            return True
        owner = getattr(obj, "user", None) or getattr(obj, "owner", None)
        return owner == request.user


class IsOwnerOrReadOnly(BasePermission):
    """
    Object-level: read is open to authenticated users;
    write only for the owner or admin.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        if request.user.role == UserRole.ADMIN:
            return True
        owner = getattr(obj, "user", None) or getattr(obj, "owner", None)
        return owner == request.user
