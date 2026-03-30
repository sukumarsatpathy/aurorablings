"""
payments.providers.registry
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
A simple, thread-safe provider registry.

Usage:
    from apps.payments.providers.registry import registry

    # Register (done in PaymentsConfig.ready)
    registry.register(CashfreeProvider())

    # Retrieve
    provider = registry.get("cashfree")
    result = provider.initiate(...)
"""
from __future__ import annotations
import threading
from .base import BasePaymentProvider


class ProviderRegistry:
    """
    Plugin-style registry for payment providers.

    Thread-safe: uses a lock for writes; reads are lock-free (dict is GIL-protected).
    """

    def __init__(self):
        self._providers: dict[str, BasePaymentProvider] = {}
        self._lock = threading.Lock()

    def register(self, provider: BasePaymentProvider) -> None:
        if not provider.name:
            raise ValueError(f"{provider.__class__.__name__} must set a `name` attribute.")
        with self._lock:
            self._providers[provider.name] = provider

    def get(self, name: str) -> BasePaymentProvider:
        try:
            return self._providers[name]
        except KeyError:
            available = ", ".join(self._providers.keys()) or "(none registered)"
            raise KeyError(
                f"Payment provider '{name}' not found. "
                f"Available providers: {available}"
            )

    def all(self) -> list[BasePaymentProvider]:
        return list(self._providers.values())

    def names(self) -> list[str]:
        return list(self._providers.keys())

    def is_registered(self, name: str) -> bool:
        return name in self._providers

    def unregister(self, name: str) -> None:
        """Used in tests to swap providers."""
        with self._lock:
            self._providers.pop(name, None)

    def __repr__(self):
        return f"<ProviderRegistry providers={self.names()}>"


# Singleton — imported everywhere
registry = ProviderRegistry()
