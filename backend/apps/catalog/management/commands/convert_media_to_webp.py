from __future__ import annotations

import os
from io import BytesIO

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.catalog.models import ProductMedia

try:
    from PIL import Image, ImageOps
except Exception:  # pragma: no cover
    Image = None
    ImageOps = None


class Command(BaseCommand):
    """Re-encode ProductMedia masters to WebP at their ORIGINAL pixel dimensions.

    Why this exists instead of `backfill_media_variants`
    ----------------------------------------------------
    `backfill_media_variants --apply` re-saves each row, which runs
    `ProductMedia.save()` -> `compress_image(max_width=1800)`. That downscales
    any master wider than 1800px and, via the `cleanup_replaced_product_media`
    pre_save signal, DELETES the original file from disk.

    This command does neither:

      * No resizing. Output width/height are asserted equal to the source.
      * No deletion. The original .jpg/.png stays on disk; only the DB pointer
        moves to the new .webp. Roll back by pointing `image` back at the old
        name.
      * No signals. Rows are written with `queryset.update()`, so `save()` and
        the pre_save cleanup never fire. Derivative fields
        (image_small/medium/large) are left exactly as they are.

    Alpha is preserved: RGBA/LA sources are encoded as WebP with an alpha
    channel rather than being flattened onto black.

    Usage:
        python manage.py convert_media_to_webp                     # dry run
        python manage.py convert_media_to_webp --apply --limit 5   # trial
        python manage.py convert_media_to_webp --apply
    """

    help = "Convert ProductMedia master images to WebP without changing resolution."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Actually write files and update rows. Without it, only reports.",
        )
        parser.add_argument(
            "--quality",
            type=int,
            default=90,
            help="WebP quality 1-100, or 0 for lossless. Default 90.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Stop after N rows (0 = no limit).",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=25,
            help="Rows per transaction. Default 25.",
        )

    # ── helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _open_source(name: str) -> "Image.Image":
        with default_storage.open(name, "rb") as fh:
            raw = fh.read()
        image = Image.open(BytesIO(raw))
        image.load()
        if ImageOps is not None:
            # Bake in EXIF orientation so the WebP renders the same way the
            # JPEG did. WebP has no orientation tag to carry it forward.
            image = ImageOps.exif_transpose(image)
        return image

    @staticmethod
    def _target_mode(image: "Image.Image") -> str:
        has_alpha = image.mode in ("RGBA", "LA") or (
            image.mode == "P" and "transparency" in image.info
        )
        return "RGBA" if has_alpha else "RGB"

    @staticmethod
    def _free_name(source_name: str) -> str:
        """`products/2026/03/<stem>.webp`, suffixed if that name is taken."""
        stem, _ = os.path.splitext(source_name)
        candidate = f"{stem}.webp"
        counter = 1
        while default_storage.exists(candidate):
            candidate = f"{stem}-webp{counter}.webp"
            counter += 1
        return candidate

    def _encode(self, image: "Image.Image", quality: int) -> bytes:
        buffer = BytesIO()
        if quality == 0:
            image.save(buffer, format="WEBP", lossless=True, method=6)
        else:
            image.save(
                buffer, format="WEBP", quality=quality, method=6, optimize=True
            )
        return buffer.getvalue()

    # ── main ─────────────────────────────────────────────────────────────

    def handle(self, *args, **options):
        if Image is None:
            raise CommandError("Pillow is not installed; cannot convert images.")

        apply_changes = bool(options["apply"])
        quality = int(options["quality"])
        if not (0 <= quality <= 100):
            raise CommandError("--quality must be between 0 and 100.")
        limit = max(0, int(options["limit"]))
        batch_size = max(1, int(options["batch_size"]))

        # `image` is non-null on this model, but a row can still hold "".
        candidates = (
            ProductMedia.objects.exclude(image="")
            .exclude(image__iendswith=".webp")
            .order_by("pk")
        )
        total = candidates.count()
        if limit:
            candidates = candidates[:limit]

        mode = "APPLY" if apply_changes else "DRY RUN"
        encoding = "lossless" if quality == 0 else f"q{quality}"
        self.stdout.write(
            f"[{mode}] {total} ProductMedia rows are not yet WebP "
            f"(encoding {encoding}, originals kept on disk)."
        )

        converted = skipped = failed = 0
        bytes_before = bytes_after = 0
        batch: list[tuple[int, str, str, bytes, tuple[int, int]]] = []

        def flush(pending):
            if not pending or not apply_changes:
                pending.clear()
                return
            with transaction.atomic():
                for pk, _old, new_name, payload, _size in pending:
                    saved = default_storage.save(new_name, ContentFile(payload))
                    ProductMedia.objects.filter(pk=pk).update(image=saved)
            pending.clear()

        for media in candidates.iterator(chunk_size=batch_size):
            name = media.image.name
            try:
                if not default_storage.exists(name):
                    self.stderr.write(f"  missing on disk, skipped: {name}")
                    skipped += 1
                    continue

                source = self._open_source(name)
                original_size = source.size
                source = source.convert(self._target_mode(source))
                payload = self._encode(source, quality)

                # Guard the one promise this command makes.
                check = Image.open(BytesIO(payload))
                if check.size != original_size:
                    self.stderr.write(
                        f"  DIMENSION MISMATCH, skipped: {name} "
                        f"{original_size} -> {check.size}"
                    )
                    failed += 1
                    continue

                new_name = self._free_name(name)
                before = default_storage.size(name)
                bytes_before += before
                bytes_after += len(payload)
                converted += 1

                self.stdout.write(
                    f"  {name} -> {new_name}  "
                    f"{original_size[0]}x{original_size[1]} kept, "
                    f"{before // 1024} KB -> {len(payload) // 1024} KB"
                )

                batch.append((media.pk, name, new_name, payload, original_size))
                if len(batch) >= batch_size:
                    flush(batch)
            except Exception as exc:  # noqa: BLE001 - report and continue
                failed += 1
                self.stderr.write(f"  FAILED {name}: {exc}")

        flush(batch)

        saved_pct = (
            100 * (bytes_before - bytes_after) / bytes_before if bytes_before else 0
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"[{mode}] converted={converted} skipped={skipped} failed={failed} "
                f"| {bytes_before // 1024} KB -> {bytes_after // 1024} KB "
                f"({saved_pct:.1f}% smaller)"
            )
        )
        if not apply_changes:
            self.stdout.write("Nothing was written. Re-run with --apply.")
