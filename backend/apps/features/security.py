from __future__ import annotations

from typing import Any

MASKED_SETTING_VALUE = "********"
SECRET_SETTING_KEYS = {"turnstile_secret_key"}


def is_secret_setting(key: str | None) -> bool:
    raw = str(key or "").strip().lower()
    if not raw:
        return False
    if raw in SECRET_SETTING_KEYS:
        return True
    return "secret" in raw


def mask_setting_value(key: str | None, value: Any) -> Any:
    if is_secret_setting(key):
        return MASKED_SETTING_VALUE
    return value


def sanitize_settings_for_response(data: Any) -> Any:
    """
    Sanitize setting payloads returned by APIs.

    Supports:
    - dict of {setting_key: value}
    - list of setting objects with {"key", "value", "typed_value"}
    - single setting object with {"key", ...}
    """
    if isinstance(data, dict):
        if "key" in data:
            key = str(data.get("key") or "")
            out = dict(data)
            if "value" in out:
                out["value"] = mask_setting_value(key, out.get("value"))
            if "typed_value" in out:
                out["typed_value"] = mask_setting_value(key, out.get("typed_value"))
            return out
        return {k: mask_setting_value(k, v) for k, v in data.items()}

    if isinstance(data, list):
        return [sanitize_settings_for_response(item) for item in data]

    return data


def sanitize_settings_for_logs(data: Any) -> dict[str, Any]:
    """
    Sanitize setting change payloads for audit metadata.
    Never includes raw values.
    """
    if isinstance(data, dict):
        keys = [str(k) for k in data.keys()]
    elif isinstance(data, list):
        keys = [str(k) for k in data]
    else:
        keys = [str(data)] if data is not None else []

    keys = [k for k in keys if k]
    return {
        "keys_updated": keys,
        "count": len(keys),
        "secret_fields_changed": [k for k in keys if is_secret_setting(k)],
    }
