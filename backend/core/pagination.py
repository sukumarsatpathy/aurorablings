from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from .response import success_response


class StandardResultsPagination(PageNumberPagination):
    """
    Default page-based pagination for all list endpoints.

    Clients can control page size via ?page_size=N (max 100).
    All responses use the standard Aurora envelope with a 'meta' block.

    Query params:
        ?page=2
        ?page_size=20
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
    page_query_param = "page"

    def get_paginated_response(self, data):
        return success_response(
            data=data,
            meta=self._build_meta(),
            message="Data retrieved successfully.",
        )

    def get_paginated_response_schema(self, schema):
        # For drf-spectacular schema generation
        return {
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "message": {"type": "string"},
                "data": schema,
                "meta": {
                    "type": "object",
                    "properties": {
                        "total_count": {"type": "integer"},
                        "total_pages": {"type": "integer"},
                        "page": {"type": "integer"},
                        "page_size": {"type": "integer"},
                        "next": {"type": "string", "nullable": True},
                        "previous": {"type": "string", "nullable": True},
                    },
                },
            },
        }

    def _build_meta(self) -> dict:
        total_pages = self.page.paginator.num_pages
        current_page = self.page.number
        return {
            "total_count": self.page.paginator.count,
            "total_pages": total_pages,
            "page": current_page,
            "page_size": self.get_page_size(self.request),
            "next": self.get_next_link(),
            "previous": self.get_previous_link(),
        }


class LargeResultsPagination(StandardResultsPagination):
    """Use for admin / reporting endpoints that need bigger pages."""
    page_size = 50
    max_page_size = 500


class SmallResultsPagination(StandardResultsPagination):
    """Use for widgets / dropdowns that only need a few items."""
    page_size = 10
    max_page_size = 50
