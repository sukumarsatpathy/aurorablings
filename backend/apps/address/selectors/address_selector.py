from __future__ import annotations

from apps.address.services.address_service import AddressService


_service = AddressService()


def lookup_by_pincode(pincode: str) -> dict:
    return _service.get_from_pincode(pincode)


def lookup_by_coordinates(lat: float, lng: float) -> dict:
    return _service.get_from_coordinates(lat, lng)

