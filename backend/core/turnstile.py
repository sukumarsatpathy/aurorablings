from __future__ import annotations

from typing import Any

import requests

from core.logging import get_logger
from apps.features import services as feature_services

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
TURNSTILE_TIMEOUT_SECONDS = 5

logger = get_logger(__name__)


def get_client_ip(request) -> str | None:
    x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded:
        return x_forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def verify_turnstile_token(*, token: str | None, remote_ip: str | None, action: str) -> bool:
    """
    Verify a Cloudflare Turnstile token.

    Behavior:
      - If disabled, always returns True (bypass).
      - If enabled and token invalid/missing/network failure, returns False (fail closed).
    """
    config = feature_services.get_turnstile_config()
    enabled = bool(config.get("enabled"))
    if not enabled:
        return True

    token_value = str(token or "").strip()
    if not token_value:
        logger.warning("turnstile_missing_token", action=action, remote_ip=remote_ip)
        return False

    secret_key = str(config.get("secret_key") or "").strip()
    if not secret_key:
        logger.error("turnstile_secret_missing", action=action)
        return False

    payload: dict[str, Any] = {
        "secret": secret_key,
        "response": token_value,
    }
    if remote_ip:
        payload["remoteip"] = remote_ip

    try:
        response = requests.post(
            TURNSTILE_VERIFY_URL,
            data=payload,
            timeout=TURNSTILE_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        body = response.json() if response.content else {}
    except Exception as exc:  # noqa: BLE001
        logger.warning("turnstile_verify_request_failed", action=action, remote_ip=remote_ip, error=str(exc))
        return False

    success = bool(body.get("success"))
    if not success:
        logger.warning(
            "turnstile_verify_failed",
            action=action,
            remote_ip=remote_ip,
            error_codes=body.get("error-codes") or [],
        )
        return False

    return True
