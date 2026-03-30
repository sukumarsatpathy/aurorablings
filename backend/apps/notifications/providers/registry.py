"""
notifications.providers.registry
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Thread-safe singleton registry for notification providers.
"""
from __future__ import annotations
import threading
from .base import BaseNotificationProvider


class NotificationProviderRegistry:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._providers = {}   # channel → provider instance
        return cls._instance

    def register(self, provider: BaseNotificationProvider) -> None:
        self._providers[provider.channel] = provider

    def get(self, channel: str) -> BaseNotificationProvider:
        if channel not in self._providers:
            raise KeyError(
                f"No notification provider registered for channel '{channel}'. "
                f"Available: {list(self._providers.keys())}"
            )
        return self._providers[channel]

    def is_registered(self, channel: str) -> bool:
        return channel in self._providers

    def all(self) -> list[BaseNotificationProvider]:
        return list(self._providers.values())


registry = NotificationProviderRegistry()
