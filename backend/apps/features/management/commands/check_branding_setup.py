"""
Why isn't the logo showing, and why won't it save?

Four things have to be true, and the UI reports much the same message for most
failures. This checks each in order and says which one is wrong:

  1. the AppSetting rows exist (saving is a PATCH — it 404s if they don't)
  2. they hold a value, and are editable
  3. MEDIA_ROOT is writable by the user this container runs as
  4. the stored file is actually on disk where nginx expects it

    python manage.py check_branding_setup
"""

from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand

from apps.features.models import AppSetting

KEYS = ("branding_logo_url", "branding_favicon_url")


class Command(BaseCommand):
    help = "Diagnose branding logo/favicon storage and saving."

    def handle(self, *args, **opts):
        ok = True

        self.stdout.write(self.style.MIGRATE_HEADING("1. Setting rows"))
        for key in KEYS:
            row = AppSetting.objects.filter(key=key).first()
            if not row:
                ok = False
                self.stdout.write(self.style.ERROR(
                    f"  {key}: MISSING - saving will 404. "
                    "apps.features migration 0004_seed_admin_settings_defaults seeds these."
                ))
                continue
            value = (row.value or "").strip()
            self.stdout.write(
                f"  {key}: {value!r} public={row.is_public} editable={row.is_editable}"
                if value else
                f"  {key}: (empty - nothing to display) editable={row.is_editable}"
            )
            if not row.is_editable:
                ok = False
                self.stdout.write(self.style.ERROR("    is_editable is False - the API will refuse to change it."))

        self.stdout.write(self.style.MIGRATE_HEADING("2. Media root"))
        media_root = Path(settings.MEDIA_ROOT)
        self.stdout.write(f"  MEDIA_ROOT = {media_root}")
        self.stdout.write(f"  MEDIA_URL  = {settings.MEDIA_URL}")
        self.stdout.write(f"  exists     = {media_root.exists()}")

        self.stdout.write(self.style.MIGRATE_HEADING("3. Can this container write an upload?"))
        try:
            saved = default_storage.save("settings/branding/.write-probe", ContentFile(b"probe"))
            self.stdout.write(self.style.SUCCESS(f"  wrote {saved} - uploads will work"))
            default_storage.delete(saved)
        except Exception as exc:  # noqa: BLE001
            ok = False
            self.stdout.write(self.style.ERROR(f"  FAILED: {exc}"))
            self.stdout.write(
                "    This is the usual cause of 'Failed to upload branding asset'. The\n"
                "    container runs as the django user (uid 101); the mounted media directory\n"
                "    must be writable by it. On the host:\n"
                "      sudo chown -R 101:101 .localprod/media   (or chmod -R a+w .localprod/media)"
            )

        self.stdout.write(self.style.MIGRATE_HEADING("4. Do the stored files exist on disk?"))
        checked = False
        for key in KEYS:
            row = AppSetting.objects.filter(key=key).first()
            value = (row.value or "").strip() if row else ""
            if not value:
                continue
            checked = True
            relative = value.split(settings.MEDIA_URL, 1)[-1] if settings.MEDIA_URL in value else value.lstrip("/")
            on_disk = media_root / relative
            if on_disk.exists():
                self.stdout.write(self.style.SUCCESS(f"  {key}: found {on_disk}"))
            else:
                ok = False
                self.stdout.write(self.style.ERROR(
                    f"  {key}: points at {value!r} but {on_disk} is missing.\n"
                    "    The row survived but the file did not - a recreated volume, or an\n"
                    "    upload that failed after the setting was written."
                ))
        if not checked:
            self.stdout.write("  (no values set yet)")

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS("Branding storage looks healthy.") if ok
            else self.style.ERROR("Branding setup has a problem - see above.")
        )
