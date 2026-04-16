from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from django.conf import settings
from django.core.files.storage import default_storage
from PIL import Image, UnidentifiedImageError

from core.exceptions import ValidationError
from core.logging import get_logger

logger = get_logger(__name__)

FORMAT_TO_MIME = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}

MIME_TO_EXTENSION = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def get_allowed_image_mime_types() -> set[str]:
    configured = getattr(settings, "IMAGE_UPLOAD_ALLOWED_MIME_TYPES", None)
    if not configured:
        configured = ("image/jpeg", "image/png", "image/webp")
    return {str(m).strip().lower() for m in configured if str(m).strip()}


def get_max_image_upload_bytes() -> int:
    return int(getattr(settings, "IMAGE_UPLOAD_MAX_BYTES", 5 * 1024 * 1024))


def _detect_image_mime(uploaded_file) -> str:
    try:
        uploaded_file.seek(0)
        with Image.open(uploaded_file) as img:
            img.verify()
            image_format = (img.format or "").upper()

        uploaded_file.seek(0)
        with Image.open(uploaded_file) as img:
            img.load()
            image_format = (img.format or image_format or "").upper()
    except UnidentifiedImageError as exc:
        raise ValidationError("Invalid image file.") from exc
    except Exception as exc:
        raise ValidationError("Corrupted or unreadable image file.") from exc
    finally:
        try:
            uploaded_file.seek(0)
        except Exception:
            pass

    detected_mime = FORMAT_TO_MIME.get(image_format)
    if not detected_mime:
        raise ValidationError("Only JPEG, PNG, and WEBP images are allowed.")
    return detected_mime


def assign_safe_image_name(uploaded_file, mime_type: str):
    extension = MIME_TO_EXTENSION.get(mime_type)
    if not extension:
        raise ValidationError("Unsupported image format.")
    uploaded_file.name = f"{uuid.uuid4().hex}{extension}"
    return uploaded_file


def validate_image_file(uploaded_file, *, max_size_bytes: int | None = None):
    if uploaded_file is None:
        raise ValidationError("Image file is required.")

    max_size = int(max_size_bytes or get_max_image_upload_bytes())
    size = int(getattr(uploaded_file, "size", 0) or 0)
    if size <= 0:
        raise ValidationError("Uploaded image is empty.")
    if size > max_size:
        max_mb = max_size / (1024 * 1024)
        raise ValidationError(f"Image size must be {max_mb:.0f} MB or smaller.")

    detected_mime = _detect_image_mime(uploaded_file).lower()
    if detected_mime not in get_allowed_image_mime_types():
        raise ValidationError("Only JPEG, PNG, and WEBP images are allowed.")

    assign_safe_image_name(uploaded_file, detected_mime)
    setattr(uploaded_file, "validated_mime_type", detected_mime)
    return uploaded_file


def delete_file_if_exists(path_or_field) -> bool:
    if not path_or_field:
        return False

    path = path_or_field
    if hasattr(path_or_field, "name"):
        path = path_or_field.name

    path = str(path or "").strip()
    if not path:
        return False

    try:
        if default_storage.exists(path):
            default_storage.delete(path)
            return True
    except Exception:
        logger.warning("file_delete_failed", path=path)
    return False


def build_media_url(file_or_url: Any, *, request=None) -> str | None:
    if not file_or_url:
        return None

    raw_url = file_or_url
    if hasattr(file_or_url, "url"):
        raw_url = file_or_url.url

    url = str(raw_url or "").strip()
    if not url:
        return None

    backend_url = str(getattr(settings, "BACKEND_URL", "") or "").rstrip("/")
    media_cdn_url = str(getattr(settings, "MEDIA_CDN_URL", "") or "").rstrip("/")

    if url.startswith("/"):
        if media_cdn_url and url.startswith(str(getattr(settings, "MEDIA_URL", "/media/") or "/media/")):
            return f"{media_cdn_url}{url}"
        if backend_url:
            return f"{backend_url}{url}"
        if request:
            return request.build_absolute_uri(url)
        return url

    if url.startswith(("http://", "https://")) and backend_url:
        parsed = urlparse(url)
        if parsed.hostname in {"backend", "backend-1", "web", "api"}:
            backend_parsed = urlparse(backend_url)
            netloc = backend_parsed.netloc or parsed.netloc
            return parsed._replace(scheme=backend_parsed.scheme or parsed.scheme, netloc=netloc).geturl()
    return url


def media_value_to_storage_path(value: str) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None

    parsed = urlparse(raw)
    path = parsed.path if parsed.scheme else raw
    media_url = str(getattr(settings, "MEDIA_URL", "/media/") or "/media/")
    if path.startswith(media_url):
        return Path(path[len(media_url):]).as_posix().lstrip("/")
    return None
