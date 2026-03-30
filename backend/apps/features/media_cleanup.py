from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings

from core.media import delete_file_if_exists, media_value_to_storage_path

DEFAULT_PROTECTED_MEDIA_PREFIXES = (
    "defaults/",
    "static/",
    "system/",
)

KNOWN_MEDIA_PREFIXES = (
    "settings/",
    "categories/",
    "brands/",
    "products/",
    "reviews/",
    "promo_banners/",
    "invoices/",
)


def _normalize_storage_path(path: str | None) -> str | None:
    raw = str(path or "").strip().replace("\\", "/").lstrip("/")
    if not raw:
        return None
    normalized = Path(raw).as_posix().lstrip("/")
    if not normalized or normalized.startswith("../") or "/../" in f"/{normalized}/":
        return None
    return normalized


def resolve_media_path(value) -> str | None:
    media_path = media_value_to_storage_path(str(value or ""))
    normalized = _normalize_storage_path(media_path)
    if normalized:
        return normalized

    raw = str(value or "").strip()
    if not raw:
        return None

    parsed = urlparse(raw)
    if parsed.scheme or raw.startswith("/"):
        return None

    candidate = _normalize_storage_path(raw)
    if not candidate:
        return None

    if candidate.startswith(KNOWN_MEDIA_PREFIXES):
        return candidate
    return None


def is_media_path(value) -> bool:
    return bool(resolve_media_path(value))


def get_protected_media_prefixes() -> tuple[str, ...]:
    configured = getattr(settings, "MEDIA_PROTECTED_PREFIXES", None)
    if not configured:
        configured = DEFAULT_PROTECTED_MEDIA_PREFIXES
    normalized: list[str] = []
    for prefix in configured:
        val = _normalize_storage_path(str(prefix or "").strip("/"))
        if not val:
            continue
        normalized.append(f"{val.rstrip('/')}/")
    return tuple(normalized)


def is_protected_media_path(path: str | None) -> bool:
    normalized = _normalize_storage_path(path)
    if not normalized:
        return True
    return normalized.startswith(get_protected_media_prefixes())


def safe_delete_media_path(path: str | None) -> bool:
    normalized = _normalize_storage_path(path)
    if not normalized:
        return False
    if is_protected_media_path(normalized):
        return False
    return delete_file_if_exists(normalized)


def cleanup_replaced_media(old_value, new_value) -> bool:
    old_path = resolve_media_path(old_value)
    new_path = resolve_media_path(new_value)

    if not old_path:
        return False
    if old_path == new_path:
        return False
    return safe_delete_media_path(old_path)
