from __future__ import annotations

import base64
import hashlib
import hmac
from typing import Any

from django.conf import settings

from core.logging import get_logger

logger = get_logger(__name__)


def _to_bytes(value: str) -> bytes:
    return (value or "").encode("utf-8")


def _resolve_cashfree_webhook_secret() -> str:
    """
    Resolve webhook secret from the same runtime sources as payment provider:
    AppSetting/ProviderConfig first, then Django settings fallback.
    """
    try:
        from apps.payments.providers.cashfree import CashfreeProvider

        provider = CashfreeProvider()
        provider._load_runtime_config()
        secret = str(provider.webhook_secret or provider.secret_key or "").strip()
        if secret:
            return secret
    except Exception:
        pass

    return str(
        getattr(settings, "CASHFREE_WEBHOOK_SECRET", "")
        or getattr(settings, "CASHFREE_SECRET_KEY", "")
        or ""
    ).strip()


def verify_cashfree_signature(*, payload: bytes, headers: dict[str, Any]) -> bool:
    """
    Verify Cashfree webhook signature.

    Primary mode follows the requested contract:
      HMAC_SHA256(secret, request.body)
    Also supports timestamp+payload signing used by some Cashfree configurations.
    """
    secret = _resolve_cashfree_webhook_secret()
    if not secret:
        logger.warning("cashfree_webhook_secret_missing")
        return False

    normalized = {str(k).lower(): str(v) for k, v in (headers or {}).items()}
    signature = normalized.get("x-webhook-signature", "")
    timestamp = normalized.get("x-webhook-timestamp", "")
    if not signature:
        logger.warning("cashfree_webhook_signature_header_missing")
        return False

    # 1) Hex digest mode: HMAC(secret, payload).hexdigest()
    hex_digest = hmac.new(_to_bytes(secret), payload or b"", hashlib.sha256).hexdigest()
    if hmac.compare_digest(hex_digest, signature):
        return True

    # 2) Base64 digest mode: base64(HMAC(secret, payload))
    b64_digest = base64.b64encode(
        hmac.new(_to_bytes(secret), payload or b"", hashlib.sha256).digest()
    ).decode()
    if hmac.compare_digest(b64_digest, signature):
        return True

    # 3) Timestamp mode: base64(HMAC(secret, timestamp + payload))
    if timestamp:
        ts_digest = base64.b64encode(
            hmac.new(_to_bytes(secret), _to_bytes(timestamp) + (payload or b""), hashlib.sha256).digest()
        ).decode()
        if hmac.compare_digest(ts_digest, signature):
            return True

    return False


def verify_cashfree_webhook(request) -> bool:
    """
    Verify signature from a Django/DRF request object.
    """
    return verify_cashfree_signature(payload=request.body, headers=dict(request.headers))
