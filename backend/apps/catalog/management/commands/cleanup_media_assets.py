from __future__ import annotations

import hashlib
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Delete oversized (>500KB) and duplicate media files under MEDIA_ROOT."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Actually delete files.")
        parser.add_argument("--max-kb", type=int, default=500, help="Max allowed size in KB.")

    def handle(self, *args, **options):
        apply_changes = bool(options["apply"])
        max_bytes = int(options["max_kb"]) * 1024
        media_root = Path(getattr(settings, "MEDIA_ROOT", "") or "").resolve()

        if not media_root.exists():
            self.stdout.write(self.style.WARNING(f"MEDIA_ROOT not found: {media_root}"))
            return

        seen_hashes: dict[str, Path] = {}
        oversized: list[Path] = []
        duplicates: list[Path] = []

        for file_path in media_root.rglob("*"):
            if not file_path.is_file():
                continue
            try:
                size = file_path.stat().st_size
                if size > max_bytes:
                    oversized.append(file_path)
                digest = hashlib.md5(file_path.read_bytes()).hexdigest()
                if digest in seen_hashes:
                    duplicates.append(file_path)
                else:
                    seen_hashes[digest] = file_path
            except Exception:
                continue

        to_delete = list(dict.fromkeys(oversized + duplicates))
        self.stdout.write(f"Oversized: {len(oversized)}")
        self.stdout.write(f"Duplicates: {len(duplicates)}")
        self.stdout.write(f"Delete candidates: {len(to_delete)}")

        if not apply_changes:
            for item in to_delete[:50]:
                self.stdout.write(f" - {item}")
            self.stdout.write(self.style.WARNING("Dry run complete. Use --apply to delete files."))
            return

        deleted = 0
        for file_path in to_delete:
            try:
                file_path.unlink(missing_ok=True)
                deleted += 1
            except Exception:
                pass
        self.stdout.write(self.style.SUCCESS(f"Deleted files: {deleted}"))

