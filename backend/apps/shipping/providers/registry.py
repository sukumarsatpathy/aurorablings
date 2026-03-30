from __future__ import annotations

import threading

from .base import BaseShippingProvider


class ShippingProviderRegistry:
    def __init__(self):
        self._providers: dict[str, BaseShippingProvider] = {}
        self._lock = threading.Lock()

    def register(self, provider: BaseShippingProvider) -> None:
        if not provider.name:
            raise ValueError("Shipping provider must define name")
        with self._lock:
            self._providers[provider.name] = provider

    def get(self, name: str) -> BaseShippingProvider:
        if name not in self._providers:
            available = ", ".join(self._providers.keys()) or "(none)"
            raise KeyError(f"Shipping provider '{name}' not registered. Available: {available}")
        return self._providers[name]

    def is_registered(self, name: str) -> bool:
        return name in self._providers


registry = ShippingProviderRegistry()
