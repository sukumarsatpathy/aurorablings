"""
core
~~~~
Public surface of Aurora Blings' core utilities.

Import from here rather than individual sub-modules:

    from core import BaseModel, SoftDeleteModel
    from core import success_response, error_response
    from core import get_logger
    from core.exceptions import NotFoundError, ValidationError
    from core.viewsets import BaseViewSet, FullCRUDViewSet, ReadOnlyViewSet
    from core.pagination import StandardResultsPagination
"""

# from core.models import BaseModel, SoftDeleteModel
# from core.response import success_response, error_response, paginated_response
# from core.logging import get_logger
#
# __all__ = [
#     "BaseModel",
#     "SoftDeleteModel",
#     "success_response",
#     "error_response",
#     "paginated_response",
#     "get_logger",
# ]
