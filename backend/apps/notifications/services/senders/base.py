from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SendResult:
    provider: str
    status: str
    provider_message_id: str = ""
    raw_response: dict | None = None


class NotificationSenderBase:
    provider_key = "other"

    def send(self, *, recipient: str, subject: str, html_body: str, text_body: str) -> SendResult:
        raise NotImplementedError

    def test_connection(self) -> tuple[bool, str]:
        raise NotImplementedError
