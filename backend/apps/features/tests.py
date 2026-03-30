from __future__ import annotations

import io
import shutil
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch

from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework.test import APIClient

from audit.models import ActivityLog, AuditAction
from apps.features.models import AppSetting
from apps.features import cache as feature_cache
from apps.features.services import TURNSTILE_CONFIG_CACHE_KEY, get_turnstile_config
from core.turnstile import verify_turnstile_token

User = get_user_model()


class TurnstileConfigTests(TestCase):
    TURNSTILE_SETTING_KEYS = (
        "turnstile_enabled",
        "turnstile_site_key",
        "turnstile_secret_key",
    )

    def setUp(self):
        self._clear_turnstile_cache()

    def tearDown(self):
        self._clear_turnstile_cache()

    def _clear_turnstile_cache(self):
        cache.delete(TURNSTILE_CONFIG_CACHE_KEY)
        for key in self.TURNSTILE_SETTING_KEYS:
            feature_cache.delete_setting_cache(key)

    @override_settings(
        TURNSTILE_ENABLED=False,
        TURNSTILE_SITE_KEY="env-site",
        TURNSTILE_SECRET_KEY="env-secret",
    )
    def test_admin_settings_override_env(self):
        AppSetting.objects.update_or_create(
            key="turnstile_enabled",
            defaults={"value": "true", "value_type": "boolean", "category": "advanced"},
        )
        AppSetting.objects.update_or_create(
            key="turnstile_site_key",
            defaults={"value": "db-site", "value_type": "string", "category": "advanced"},
        )
        AppSetting.objects.update_or_create(
            key="turnstile_secret_key",
            defaults={"value": "db-secret", "value_type": "string", "category": "advanced"},
        )

        data = get_turnstile_config()
        self.assertTrue(data["enabled"])
        self.assertEqual(data["site_key"], "db-site")
        self.assertEqual(data["secret_key"], "db-secret")

    @override_settings(
        TURNSTILE_ENABLED=True,
        TURNSTILE_SITE_KEY="env-site",
        TURNSTILE_SECRET_KEY="env-secret",
    )
    def test_env_fallback_when_admin_missing(self):
        AppSetting.objects.filter(key__in=self.TURNSTILE_SETTING_KEYS).delete()
        self._clear_turnstile_cache()
        data = get_turnstile_config()
        self.assertTrue(data["enabled"])
        self.assertEqual(data["site_key"], "env-site")
        self.assertEqual(data["secret_key"], "env-secret")

    @override_settings(
        TURNSTILE_ENABLED=True,
        TURNSTILE_SITE_KEY="env-site",
        TURNSTILE_SECRET_KEY="env-secret",
    )
    def test_public_runtime_endpoint_never_exposes_secret(self):
        client = APIClient()
        response = client.get("/api/settings/public")
        self.assertEqual(response.status_code, 200)
        payload = response.json().get("data", {})
        self.assertIn("turnstile_enabled", payload)
        self.assertIn("turnstile_site_key", payload)
        self.assertNotIn("turnstile_secret_key", payload)


class TurnstileVerificationTests(TestCase):
    TURNSTILE_SETTING_KEYS = (
        "turnstile_enabled",
        "turnstile_site_key",
        "turnstile_secret_key",
    )

    def setUp(self):
        cache.delete(TURNSTILE_CONFIG_CACHE_KEY)
        for key in self.TURNSTILE_SETTING_KEYS:
            feature_cache.delete_setting_cache(key)

    def tearDown(self):
        cache.delete(TURNSTILE_CONFIG_CACHE_KEY)
        for key in self.TURNSTILE_SETTING_KEYS:
            feature_cache.delete_setting_cache(key)

    @override_settings(TURNSTILE_ENABLED=False, TURNSTILE_SITE_KEY="", TURNSTILE_SECRET_KEY="")
    def test_verification_bypasses_when_disabled(self):
        self.assertTrue(verify_turnstile_token(token="", remote_ip=None, action="test.disabled"))

    @override_settings(TURNSTILE_ENABLED=True, TURNSTILE_SITE_KEY="site", TURNSTILE_SECRET_KEY="secret")
    @patch("core.turnstile.requests.post")
    def test_verification_fails_for_invalid_token(self, mock_post):
        AppSetting.objects.filter(key__in=self.TURNSTILE_SETTING_KEYS).delete()
        cache.delete(TURNSTILE_CONFIG_CACHE_KEY)
        for key in self.TURNSTILE_SETTING_KEYS:
            feature_cache.delete_setting_cache(key)

        mock_response = Mock()
        mock_response.content = b'{"success": false, "error-codes": ["invalid-input-response"]}'
        mock_response.json.return_value = {"success": False, "error-codes": ["invalid-input-response"]}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        self.assertFalse(verify_turnstile_token(token="bad-token", remote_ip="1.2.3.4", action="test.invalid"))


class BulkSettingsSecurityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_user(
            email="admin@example.com",
            password="password123",
            role="admin",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_authenticate(user=self.admin_user)
        AppSetting.objects.update_or_create(
            key="turnstile_secret_key",
            defaults={"value": "old-secret", "value_type": "string", "category": "advanced"},
        )
        AppSetting.objects.update_or_create(
            key="turnstile_site_key",
            defaults={"value": "old-site", "value_type": "string", "category": "advanced"},
        )

    def test_bulk_update_masks_secret_in_response(self):
        response = self.client.post(
            "/api/v1/features/settings/bulk/",
            {
                "settings": {
                    "turnstile_secret_key": "new-secret-value",
                    "turnstile_site_key": "new-site-value",
                }
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json().get("data", {})
        self.assertEqual(payload.get("turnstile_secret_key"), "********")
        self.assertEqual(payload.get("turnstile_site_key"), "new-site-value")

        secret_row = AppSetting.objects.get(key="turnstile_secret_key")
        self.assertEqual(secret_row.value, "new-secret-value")

    def test_bulk_update_audit_metadata_does_not_store_secret_values(self):
        response = self.client.post(
            "/api/v1/features/settings/bulk/",
            {"settings": {"turnstile_secret_key": "audit-secret-check"}},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

        log = ActivityLog.objects.filter(
            action=AuditAction.UPDATE,
            entity_type="setting",
            entity_id="bulk",
        ).order_by("-created_at").first()
        self.assertIsNotNone(log)
        metadata = log.metadata or {}
        serialized = str(metadata)
        self.assertNotIn("audit-secret-check", serialized)
        self.assertEqual(metadata.get("count"), 1)
        self.assertIn("turnstile_secret_key", metadata.get("keys_updated", []))
        self.assertIn("turnstile_secret_key", metadata.get("secret_fields_changed", []))
        self.assertEqual(metadata.get("status"), "success")

    def test_bulk_update_non_secret_values_still_return_normally(self):
        AppSetting.objects.update_or_create(
            key="site.frontend_url",
            defaults={"value": "http://localhost:5173", "value_type": "string", "category": "general"},
        )
        response = self.client.post(
            "/api/v1/features/settings/bulk/",
            {"settings": {"site.frontend_url": "https://aurorablings.com"}},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json().get("data", {})
        self.assertEqual(payload.get("site.frontend_url"), "https://aurorablings.com")


class SettingUploadSecurityTests(TestCase):
    def setUp(self):
        self._tmp_media = tempfile.mkdtemp(prefix="aurora-settings-upload-")
        self.override_media = override_settings(
            MEDIA_ROOT=self._tmp_media,
            IMAGE_UPLOAD_MAX_BYTES=5 * 1024 * 1024,
        )
        self.override_media.enable()
        self.addCleanup(self.override_media.disable)
        self.addCleanup(lambda: shutil.rmtree(self._tmp_media, ignore_errors=True))

        self.client = APIClient()
        self.admin_user = User.objects.create_user(
            email="settings-admin@example.com",
            password="password123",
            role="admin",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_authenticate(user=self.admin_user)

    def _image_file(self, *, name="settings.jpg", image_format="JPEG"):
        buffer = io.BytesIO()
        Image.new("RGB", (80, 80), color=(20, 180, 100)).save(buffer, format=image_format)
        content_type = {
            "JPEG": "image/jpeg",
            "PNG": "image/png",
            "WEBP": "image/webp",
        }.get(image_format.upper(), "image/jpeg")
        return SimpleUploadedFile(name, buffer.getvalue(), content_type=content_type)

    def test_valid_settings_upload_success(self):
        response = self.client.post(
            "/api/v1/features/settings/upload/",
            {"file": self._image_file(name="brand.png", image_format="PNG"), "key": "branding_logo"},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)
        payload = response.json().get("data", {})
        self.assertIn("/media/settings/branding/", str(payload.get("url", "")))
        self.assertIn("settings/branding/", str(payload.get("path", "")))

    def test_fake_image_rejected(self):
        fake = SimpleUploadedFile("fake.jpg", b"not-image", content_type="image/jpeg")
        response = self.client.post(
            "/api/v1/features/settings/upload/",
            {"file": fake},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)

    def test_large_file_rejected(self):
        large = SimpleUploadedFile("large.jpg", b"a" * (6 * 1024 * 1024), content_type="image/jpeg")
        response = self.client.post(
            "/api/v1/features/settings/upload/",
            {"file": large},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)

    def test_corrupted_file_rejected(self):
        valid = self._image_file(name="ok.webp", image_format="WEBP")
        corrupted = SimpleUploadedFile("bad.webp", valid.read()[:10], content_type="image/webp")
        response = self.client.post(
            "/api/v1/features/settings/upload/",
            {"file": corrupted},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)


class BulkSettingsMediaCleanupTests(TestCase):
    def setUp(self):
        self._tmp_media = tempfile.mkdtemp(prefix="aurora-bulk-settings-media-")
        self.override_media = override_settings(MEDIA_ROOT=self._tmp_media)
        self.override_media.enable()
        self.addCleanup(self.override_media.disable)
        self.addCleanup(lambda: shutil.rmtree(self._tmp_media, ignore_errors=True))

        self.client = APIClient()
        self.admin_user = User.objects.create_user(
            email="bulk-media-admin@example.com",
            password="password123",
            role="admin",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_authenticate(user=self.admin_user)

    def _touch_media_file(self, relative_path: str) -> str:
        target = Path(self._tmp_media) / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"test-file")
        return str(target)

    def test_bulk_update_replacing_media_deletes_old_file(self):
        old_relative = "settings/branding/old-bulk.jpg"
        old_abs = self._touch_media_file(old_relative)
        AppSetting.objects.update_or_create(
            key="branding_logo_url",
            defaults={
                "value": f"/media/{old_relative}",
                "value_type": "string",
                "category": "branding",
                "is_editable": True,
            },
        )

        response = self.client.post(
            "/api/v1/features/settings/bulk/",
            {"settings": {"branding_logo_url": "/media/settings/branding/new-bulk.jpg"}},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Path(old_abs).exists())

    def test_bulk_update_unchanged_media_does_not_delete_file(self):
        relative = "settings/branding/same-bulk.jpg"
        abs_path = self._touch_media_file(relative)
        AppSetting.objects.update_or_create(
            key="branding_logo_url",
            defaults={
                "value": f"/media/{relative}",
                "value_type": "string",
                "category": "branding",
                "is_editable": True,
            },
        )

        response = self.client.post(
            "/api/v1/features/settings/bulk/",
            {"settings": {"branding_logo_url": f"/media/{relative}"}},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Path(abs_path).exists())

    def test_bulk_update_non_media_setting_behaves_normally(self):
        AppSetting.objects.update_or_create(
            key="site.frontend_url",
            defaults={"value": "http://localhost:5173", "value_type": "string", "category": "general"},
        )
        response = self.client.post(
            "/api/v1/features/settings/bulk/",
            {"settings": {"site.frontend_url": "https://aurorablings.com"}},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json().get("data", {})
        self.assertEqual(payload.get("site.frontend_url"), "https://aurorablings.com")


class OrphanMediaCommandTests(TestCase):
    def setUp(self):
        self._tmp_media = tempfile.mkdtemp(prefix="aurora-orphan-media-")
        self.override_media = override_settings(MEDIA_ROOT=self._tmp_media)
        self.override_media.enable()
        self.addCleanup(self.override_media.disable)
        self.addCleanup(lambda: shutil.rmtree(self._tmp_media, ignore_errors=True))

    def _touch(self, relative_path: str) -> Path:
        path = Path(self._tmp_media) / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"orphan-check")
        return path

    def test_orphan_cleanup_dry_run_reports_without_deleting(self):
        referenced = self._touch("settings/branding/keep.jpg")
        orphan = self._touch("settings/branding/orphan.jpg")
        protected = self._touch("defaults/protected.jpg")

        AppSetting.objects.update_or_create(
            key="branding_logo_url",
            defaults={"value": "/media/settings/branding/keep.jpg", "value_type": "string", "category": "branding"},
        )

        stdout = StringIO()
        call_command("cleanup_orphan_media", "--dry-run", stdout=stdout)
        output = stdout.getvalue()

        self.assertIn("orphan_files=", output)
        self.assertIn("orphan_preview:", output)
        self.assertTrue(referenced.exists())
        self.assertTrue(orphan.exists())
        self.assertTrue(protected.exists())

    def test_orphan_cleanup_delete_removes_true_orphans_only(self):
        referenced = self._touch("settings/branding/keep-delete.jpg")
        orphan = self._touch("settings/branding/orphan-delete.jpg")
        protected = self._touch("defaults/protected-delete.jpg")

        AppSetting.objects.update_or_create(
            key="branding_logo_url",
            defaults={"value": "/media/settings/branding/keep-delete.jpg", "value_type": "string", "category": "branding"},
        )

        stdout = StringIO()
        call_command("cleanup_orphan_media", "--delete", stdout=stdout)
        output = stdout.getvalue()

        self.assertIn("deleted=", output)
        self.assertTrue(referenced.exists())
        self.assertFalse(orphan.exists())
        self.assertTrue(protected.exists())
