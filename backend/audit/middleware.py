from __future__ import annotations

from audit.request_context import reset_current_request, set_current_request


class AuditRequestContextMiddleware:
    """Expose current request through contextvars for service-layer logging."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = set_current_request(request)
        try:
            return self.get_response(request)
        finally:
            reset_current_request(token)
