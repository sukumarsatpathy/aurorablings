from rest_framework.permissions import BasePermission


class IsReviewOwner(BasePermission):
    message = "You can only modify your own review."

    def has_object_permission(self, request, view, obj):
        return bool(request.user and request.user.is_authenticated and obj.user_id == request.user.id)
