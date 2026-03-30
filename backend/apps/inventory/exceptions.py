"""
inventory.exceptions
~~~~~~~~~~~~~~~~~~~~
Domain-specific exceptions for the stock system.
All inherit from core.exceptions so the global handler picks them up.
"""

from core.exceptions import AuroraBaseException, ValidationError
from rest_framework import status


class InsufficientStockError(AuroraBaseException):
    """
    Raised when a requested quantity cannot be fulfilled.

    Always include `available` and `requested` in `extra`
    so the caller (and client) can show a meaningful message.

    Example:
        raise InsufficientStockError(
            sku="SKU-001",
            requested=5,
            available=2,
        )
    """

    status_code   = status.HTTP_409_CONFLICT
    default_code  = "insufficient_stock"

    def __init__(self, sku: str, requested: int, available: int, warehouse: str = "default"):
        message = (
            f"Insufficient stock for SKU '{sku}'. "
            f"Requested: {requested}, Available: {available}."
        )
        super().__init__(
            message=message,
            code=self.default_code,
            extra={
                "sku": sku,
                "requested": requested,
                "available": available,
                "warehouse": warehouse,
            },
        )


class StockReservationError(AuroraBaseException):
    """Raised when a reservation cannot be created or released."""
    status_code  = status.HTTP_409_CONFLICT
    default_code = "reservation_error"


class InvalidMovementError(ValidationError):
    """Raised when a stock movement has an invalid quantity or type."""
    default_code = "invalid_movement"


class WarehouseNotFoundError(AuroraBaseException):
    status_code  = status.HTTP_404_NOT_FOUND
    default_code = "warehouse_not_found"
