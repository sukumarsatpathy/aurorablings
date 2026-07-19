from __future__ import annotations

import os
import uuid
from io import BytesIO
from pathlib import Path

from django.core.files.base import ContentFile

try:
    from PIL import Image, ImageOps
except Exception:  # pragma: no cover
    Image = None
    ImageOps = None


def _read_file_bytes(file_obj) -> bytes:
    if hasattr(file_obj, "seek"):
        try:
            file_obj.seek(0)
        except Exception:
            pass
    if hasattr(file_obj, "read"):
        data = file_obj.read()
    else:
        data = bytes(file_obj or b"")
    if hasattr(file_obj, "seek"):
        try:
            file_obj.seek(0)
        except Exception:
            pass
    return data


def _to_rgb(image: "Image.Image") -> "Image.Image":
    if ImageOps is not None:
        image = ImageOps.exif_transpose(image)
    if image.mode in ("RGB", "L"):
        return image.convert("RGB")
    return image.convert("RGB")


def _save_webp_content(image: "Image.Image", *, quality: int = 74) -> ContentFile:
    buffer = BytesIO()
    image.save(buffer, format="WEBP", quality=quality, optimize=True, method=6)
    return ContentFile(buffer.getvalue())


# AVIF quality is NOT on the same scale as WebP quality. Passing the WebP
# number (74) through to AVIF produces files that are LARGER than the WebP
# equivalent, which defeats the entire point. Roughly, AVIF q50 lands near
# WebP q75 in perceived quality. Tune against real banner images, not
# synthetic ones — the correct value is content-dependent.
AVIF_QUALITY_DEFAULT = 50

# 0 = slowest/smallest, 10 = fastest/largest. Generation runs synchronously
# inside PromoBanner.save(), so this trades a little file size for not making
# an admin upload hang. Measured ~8x faster than speed=0 for negligible size.
AVIF_SPEED_DEFAULT = 6


def avif_encoder_available() -> bool:
    """True if this Pillow build can actually encode AVIF.

    Native AVIF support landed in Pillow 11.3. requirements.txt previously
    allowed >=10.2, so this cannot be assumed from the import succeeding.
    """
    if Image is None:
        return False
    try:
        from PIL import features

        if features.check("avif"):
            return True
    except Exception:
        pass
    return "AVIF" in getattr(Image, "SAVE", {})


def _save_avif_content(
    image: "Image.Image",
    *,
    quality: int = AVIF_QUALITY_DEFAULT,
    speed: int = AVIF_SPEED_DEFAULT,
) -> ContentFile:
    buffer = BytesIO()
    image.save(buffer, format="AVIF", quality=quality, speed=speed)
    return ContentFile(buffer.getvalue())


def compress_image(
    source_file,
    *,
    output_dir: str,
    max_width: int = 1600,
    quality: int = 74,
    file_stem: str | None = None,
) -> tuple[str, ContentFile]:
    if Image is None:
        raw = _read_file_bytes(source_file)
        stem = file_stem or f"{uuid.uuid4().hex}"
        filename = os.path.join(output_dir, f"{stem}.bin").replace("\\", "/")
        return filename, ContentFile(raw)

    raw = _read_file_bytes(source_file)
    image = _to_rgb(Image.open(BytesIO(raw)))

    if image.width > max_width:
        ratio = max_width / float(image.width)
        target_height = max(1, int(image.height * ratio))
        image = image.resize((max_width, target_height), Image.Resampling.LANCZOS)

    stem = file_stem or f"{uuid.uuid4().hex}"
    filename = os.path.join(output_dir, f"{stem}.webp").replace("\\", "/")
    return filename, _save_webp_content(image, quality=quality)


def generate_responsive_variants(
    source_file,
    *,
    output_dir: str,
    base_stem: str | None = None,
    widths: tuple[int, int, int] = (480, 768, 1200),
    quality: int = 72,
) -> dict[str, tuple[str, ContentFile]]:
    if Image is None:
        raw = _read_file_bytes(source_file)
        stem = base_stem or f"{uuid.uuid4().hex}"
        return {
            "small": (os.path.join(output_dir, f"{stem}-480.bin").replace("\\", "/"), ContentFile(raw)),
            "medium": (os.path.join(output_dir, f"{stem}-768.bin").replace("\\", "/"), ContentFile(raw)),
            "large": (os.path.join(output_dir, f"{stem}-1200.bin").replace("\\", "/"), ContentFile(raw)),
        }

    raw = _read_file_bytes(source_file)
    base_image = _to_rgb(Image.open(BytesIO(raw)))
    stem = base_stem or f"{uuid.uuid4().hex}"
    labels = ("small", "medium", "large")
    variants: dict[str, tuple[str, ContentFile]] = {}

    for label, target_width in zip(labels, widths):
        if base_image.width > target_width:
            ratio = target_width / float(base_image.width)
            target_height = max(1, int(base_image.height * ratio))
            resized = base_image.resize((target_width, target_height), Image.Resampling.LANCZOS)
        else:
            resized = base_image.copy()
        filename = os.path.join(output_dir, f"{stem}-{target_width}.webp").replace("\\", "/")
        variants[label] = (filename, _save_webp_content(resized, quality=quality))

    return variants


def generate_avif_variants(
    source_file,
    *,
    output_dir: str,
    base_stem: str | None = None,
    widths: tuple[int, int, int] = (480, 768, 1200),
    quality: int = AVIF_QUALITY_DEFAULT,
    speed: int = AVIF_SPEED_DEFAULT,
) -> dict[str, tuple[str, ContentFile]]:
    """AVIF siblings of generate_responsive_variants().

    Deliberately returns {} rather than raising or writing .bin files when the
    encoder is missing. AVIF is purely additive here: the <picture> element in
    PromoBannerCard drops the AVIF <source> when these are absent and every
    visitor falls through to the WebP srcSet. That is a safe degradation, unlike
    the .bin fallback in the functions above, which produces unservable files.
    """
    if Image is None or not avif_encoder_available():
        return {}

    raw = _read_file_bytes(source_file)
    base_image = _to_rgb(Image.open(BytesIO(raw)))
    stem = base_stem or f"{uuid.uuid4().hex}"
    labels = ("small", "medium", "large")
    variants: dict[str, tuple[str, ContentFile]] = {}

    for label, target_width in zip(labels, widths):
        if base_image.width > target_width:
            ratio = target_width / float(base_image.width)
            target_height = max(1, int(base_image.height * ratio))
            resized = base_image.resize((target_width, target_height), Image.Resampling.LANCZOS)
        else:
            resized = base_image.copy()
        filename = os.path.join(output_dir, f"{stem}-{target_width}.avif").replace("\\", "/")
        variants[label] = (filename, _save_avif_content(resized, quality=quality, speed=speed))

    return variants


def build_srcset(*, small_url: str | None, medium_url: str | None, large_url: str | None) -> str:
    sources: list[str] = []
    if small_url:
        sources.append(f"{small_url} 480w")
    if medium_url:
        sources.append(f"{medium_url} 768w")
    if large_url:
        sources.append(f"{large_url} 1200w")
    return ", ".join(sources)

