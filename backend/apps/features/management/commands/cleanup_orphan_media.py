from __future__ import annotations

from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import FileField

from apps.features.media_cleanup import (
    is_protected_media_path,
    resolve_media_path,
    safe_delete_media_path,
)
from apps.features.models import AppSetting


class Command(BaseCommand):
    help = "Scan MEDIA_ROOT for orphan files and optionally delete them."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report orphan files without deleting (default behavior).",
        )
        parser.add_argument(
            "--delete",
            action="store_true",
            help="Delete orphan files (explicit opt-in).",
        )

    def handle(self, *args, **options):
        media_root = Path(getattr(settings, "MEDIA_ROOT", "")).resolve()
        if not media_root.exists():
            self.stdout.write(self.style.WARNING(f"MEDIA_ROOT does not exist: {media_root}"))
            return

        should_delete = bool(options.get("delete"))
        dry_run = bool(options.get("dry_run")) or not should_delete

        referenced_paths = self._collect_referenced_paths()
        all_files = self._collect_all_media_files(media_root)

        orphan_candidates = sorted(p for p in all_files if p not in referenced_paths)
        protected_orphans = [p for p in orphan_candidates if is_protected_media_path(p)]
        deletable_orphans = [p for p in orphan_candidates if p not in protected_orphans]

        deleted_count = 0
        if should_delete:
            for orphan in deletable_orphans:
                if safe_delete_media_path(orphan):
                    deleted_count += 1

        mode = "DRY-RUN" if dry_run else "DELETE"
        self.stdout.write(self.style.SUCCESS(f"[cleanup_orphan_media] mode={mode}"))
        self.stdout.write(f"media_root={media_root}")
        self.stdout.write(f"referenced_files={len(referenced_paths)}")
        self.stdout.write(f"total_media_files={len(all_files)}")
        self.stdout.write(f"orphan_files={len(orphan_candidates)}")
        self.stdout.write(f"protected_orphans_skipped={len(protected_orphans)}")
        self.stdout.write(f"deletable_orphans={len(deletable_orphans)}")
        self.stdout.write(f"deleted={deleted_count}")

        preview_limit = 20
        if orphan_candidates:
            self.stdout.write("orphan_preview:")
            for orphan in orphan_candidates[:preview_limit]:
                tag = " (protected)" if orphan in protected_orphans else ""
                self.stdout.write(f" - {orphan}{tag}")

    def _collect_all_media_files(self, media_root: Path) -> set[str]:
        paths: set[str] = set()
        for file_path in media_root.rglob("*"):
            if not file_path.is_file():
                continue
            rel = file_path.relative_to(media_root).as_posix().lstrip("/")
            if rel:
                paths.add(rel)
        return paths

    def _collect_referenced_paths(self) -> set[str]:
        references: set[str] = set()

        for setting in AppSetting.objects.only("value"):
            media_path = resolve_media_path(setting.value)
            if media_path:
                references.add(media_path)

        for model in apps.get_models():
            file_fields = [
                field
                for field in model._meta.get_fields()
                if isinstance(field, FileField)
            ]
            if not file_fields:
                continue

            manager = getattr(model, "_base_manager", None) or model._default_manager
            queryset = manager.all()
            for field in file_fields:
                for raw_value in queryset.values_list(field.name, flat=True):
                    media_path = resolve_media_path(raw_value)
                    if media_path:
                        references.add(media_path)

        return references
