"""
features.decorators
~~~~~~~~~~~~~~~~~~~
View-level guards for feature-gated endpoints.

Usage:
    from apps.features.decorators import feature_required

    @feature_required("payment_stripe")
    class StripePaymentView(APIView):
        ...

    # Or on a function view:
    @feature_required("advanced_analytics")
    def analytics_view(request):
        ...

If the feature is disabled, returns HTTP 503 with a clear error message.
"""
from functools import wraps
from django.http import JsonResponse
from rest_framework import status


def feature_required(feature_code: str):
    """
    Class or function decorator that returns 503 if the feature is disabled.

    The DRF user_id is resolved from request.user.id if authenticated.
    """
    def decorator(view):
        # ── Class-based view (wraps dispatch) ────────────────
        if isinstance(view, type):
            original_dispatch = view.dispatch

            def gated_dispatch(self_inner, request, *args, **kwargs):
                from apps.features.services import is_feature_enabled, FeatureDisabledError
                user_id = request.user.id if request.user and request.user.is_authenticated else None
                if not is_feature_enabled(feature_code, user_id=user_id):
                    return JsonResponse(
                        {
                            "success":   False,
                            "error":     f"Feature '{feature_code}' is currently disabled.",
                            "error_code": "feature_disabled",
                        },
                        status=status.HTTP_503_SERVICE_UNAVAILABLE,
                    )
                return original_dispatch(self_inner, request, *args, **kwargs)

            view.dispatch = gated_dispatch
            return view

        # ── Function-based view ───────────────────────────────
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            from apps.features.services import is_feature_enabled
            user_id = request.user.id if request.user and request.user.is_authenticated else None
            if not is_feature_enabled(feature_code, user_id=user_id):
                return JsonResponse(
                    {
                        "success":   False,
                        "error":     f"Feature '{feature_code}' is currently disabled.",
                        "error_code": "feature_disabled",
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            return view(request, *args, **kwargs)

        return wrapped

    return decorator
