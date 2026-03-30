"""
notifications.providers.base
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Abstract base for all notification providers.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class DeliveryResult:
    success:      bool
    provider_ref: str = ""   # provider's message ID
    error:        str = ""
    raw_response: dict = None

    def __post_init__(self):
        if self.raw_response is None:
            self.raw_response = {}


class BaseNotificationProvider(ABC):
    """
    All notification channel providers must inherit from this class.

    channel      – matches NotificationChannel constants
    display_name – shown in admin / logs
    """

    channel: str = ""
    display_name: str = ""

    @abstractmethod
    def send(
        self,
        *,
        recipient: str,        # email address OR phone number
        subject: str = "",     # email subject (ignored by SMS/WhatsApp)
        body: str,
        html_body: str = "",   # HTML variant (email only)
        metadata: dict = None, # extra provider-specific options
    ) -> DeliveryResult:
        """Send a single notification. Must be idempotent (provider-side dedup via ref)."""
        ...

    def is_configured(self) -> bool:
        """Return True if the necessary credentials are present."""
        return True
