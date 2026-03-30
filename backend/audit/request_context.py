from __future__ import annotations

from contextvars import ContextVar

from django.http import HttpRequest


_current_request: ContextVar[HttpRequest | None] = ContextVar("audit_current_request", default=None)


def set_current_request(request: HttpRequest | None) -> object:
    return _current_request.set(request)


def reset_current_request(token: object) -> None:
    _current_request.reset(token)


def get_current_request() -> HttpRequest | None:
    return _current_request.get()
