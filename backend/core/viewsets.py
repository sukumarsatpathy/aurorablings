from rest_framework import viewsets, mixins, status
from rest_framework.response import Response

from .exceptions import NotFoundError
from .logging import get_logger
from .pagination import StandardResultsPagination
from .response import success_response, error_response

logger = get_logger(__name__)


class BaseViewSet(viewsets.GenericViewSet):
    """
    Base viewset every Aurora Blings API view should extend.

    Provides:
        - request_id propagation from the tracing middleware
        - get_object() override that raises our typed NotFoundError
        - helper shortcuts: ok(), created(), no_content(), bad_request()
        - integrated structured logging on each action
        - StandardResultsPagination pre-wired

    Usage:
        class ProductViewSet(BaseViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
            queryset = Product.objects.all()
            serializer_class = ProductSerializer
    """

    pagination_class = StandardResultsPagination

    # ── Helpers ────────────────────────────────────────────────

    @property
    def request_id(self) -> str:
        return getattr(self.request, "request_id", "N/A")

    def get_object(self):
        """Override to raise our typed NotFoundError instead of Http404."""
        try:
            return super().get_object()
        except Exception as exc:
            from django.http import Http404
            if isinstance(exc, Http404):
                model_name = self.queryset.model.__name__ if self.queryset is not None else "Object"
                raise NotFoundError(message=f"{model_name} not found.")
            raise

    # ── Response shortcuts ─────────────────────────────────────

    def ok(self, data=None, message="Request successful.") -> Response:
        return success_response(data=data, message=message, request_id=self.request_id)

    def created(self, data=None, message="Created successfully.") -> Response:
        return success_response(data=data, message=message, status_code=status.HTTP_201_CREATED, request_id=self.request_id)

    def no_content(self) -> Response:
        return Response(status=status.HTTP_204_NO_CONTENT)

    def bad_request(self, message="Bad request.", error_code="bad_request", errors=None) -> Response:
        return error_response(
            message=message,
            error_code=error_code,
            errors=errors,
            status_code=status.HTTP_400_BAD_REQUEST,
            request_id=self.request_id,
        )

    # ── Pagination helper ──────────────────────────────────────

    def paginate(self, queryset, serializer_class):
        """
        Shortcut: paginate a queryset and return an envelope response.

        Usage:
            def list(self, request):
                qs = self.get_queryset()
                return self.paginate(qs, ProductSerializer)
        """
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = serializer_class(page, many=True, context={"request": self.request})
            return self.get_paginated_response(serializer.data)
        serializer = serializer_class(queryset, many=True, context={"request": self.request})
        return self.ok(data=serializer.data)


# ─────────────────────────────────────────────────────────────
#  Pre-composed CRUD viewsets
# ─────────────────────────────────────────────────────────────

class ReadOnlyViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    BaseViewSet,
):
    """Provides list + retrieve only."""


class FullCRUDViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    mixins.ListModelMixin,
    BaseViewSet,
):
    """
    Full CRUD viewset with all standard actions.
    Extend this for resources that need create, read, update, delete.
    """

    def perform_destroy(self, instance):
        """Calls model-level .delete() — honours soft-delete if model uses it."""
        instance.delete()
        logger.info("record_deleted", model=instance.__class__.__name__, id=str(instance.pk), request_id=self.request_id)

    def destroy(self, request, *args, **kwargs):
        """Override to return 200 with message instead of 204."""
        instance = self.get_object()
        self.perform_destroy(instance)
        return self.ok(message="Deleted successfully.")
