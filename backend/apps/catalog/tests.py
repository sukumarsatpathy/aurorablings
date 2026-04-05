from __future__ import annotations

import io
import shutil
import tempfile
from pathlib import Path

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from apps.catalog.models import Category

User = get_user_model()


def make_image_file(name: str = "image.jpg", *, image_format: str = "JPEG", size=(64, 64)) -> SimpleUploadedFile:
    buffer = io.BytesIO()
    Image.new("RGB", size, color=(120, 80, 180)).save(buffer, format=image_format)
    content_type = {
        "JPEG": "image/jpeg",
        "PNG": "image/png",
        "WEBP": "image/webp",
    }.get(image_format.upper(), "image/jpeg")
    return SimpleUploadedFile(name=name, content=buffer.getvalue(), content_type=content_type)


class CatalogUploadSecurityTests(APITestCase):
    def setUp(self):
        self._tmp_media = tempfile.mkdtemp(prefix="aurora-media-tests-")
        self.override_media = override_settings(
            MEDIA_ROOT=self._tmp_media,
            IMAGE_UPLOAD_MAX_BYTES=5 * 1024 * 1024,
        )
        self.override_media.enable()
        self.addCleanup(self.override_media.disable)
        self.addCleanup(lambda: shutil.rmtree(self._tmp_media, ignore_errors=True))

        self.admin = User.objects.create_user(
            email="admin-upload@example.com",
            password="password123",
            role="admin",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_authenticate(user=self.admin)
        self.categories_url = "/api/v1/catalog/categories/"

    def test_valid_image_upload_succeeds(self):
        payload = {
            "name": "Rings",
            "description": "Rings category",
            "image": make_image_file("rings.jpg", image_format="JPEG"),
        }
        response = self.client.post(self.categories_url, payload, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        category = Category.all_objects.get(name="Rings")
        self.assertTrue(bool(category.image))
        self.assertTrue(Path(category.image.path).exists())

    def test_fake_image_rejected(self):
        fake = SimpleUploadedFile("fake.jpg", b"not-an-image", content_type="image/jpeg")
        payload = {"name": "Fake", "image": fake}
        response = self.client.post(self.categories_url, payload, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_large_file_rejected(self):
        large_bytes = b"a" * (6 * 1024 * 1024)
        fake_large = SimpleUploadedFile("large.jpg", large_bytes, content_type="image/jpeg")
        payload = {"name": "Large", "image": fake_large}
        response = self.client.post(self.categories_url, payload, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_corrupted_image_rejected(self):
        valid = make_image_file("valid.png", image_format="PNG")
        corrupted = SimpleUploadedFile("corrupt.png", valid.read()[:18], content_type="image/png")
        payload = {"name": "Corrupt", "image": corrupted}
        response = self.client.post(self.categories_url, payload, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_replace_image_deletes_old_file(self):
        create_response = self.client.post(
            self.categories_url,
            {"name": "ReplaceMe", "image": make_image_file("old.jpg", image_format="JPEG")},
            format="multipart",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        category_id = create_response.data["data"]["id"]
        category = Category.all_objects.get(id=category_id)
        old_path = category.image.path
        self.assertTrue(Path(old_path).exists())

        patch_response = self.client.patch(
            f"{self.categories_url}{category_id}/",
            {"image": make_image_file("new.webp", image_format="WEBP")},
            format="multipart",
        )
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)

        category.refresh_from_db()
        self.assertNotEqual(category.image.path, old_path)
        self.assertFalse(Path(old_path).exists())
        self.assertTrue(Path(category.image.path).exists())

    def test_delete_category_deletes_file(self):
        response = self.client.post(
            self.categories_url,
            {"name": "DeleteMe", "image": make_image_file("delete.jpg", image_format="JPEG")},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        category_id = response.data["data"]["id"]
        category = Category.all_objects.get(id=category_id)
        image_path = category.image.path
        self.assertTrue(Path(image_path).exists())

        delete_response = self.client.delete(f"{self.categories_url}{category_id}/")
        self.assertEqual(delete_response.status_code, status.HTTP_200_OK)
        self.assertFalse(Path(image_path).exists())


class CatalogCategoryListTests(APITestCase):
    def test_latest_query_returns_newest_categories_first(self):
        older = Category.all_objects.create(name="Older Category", slug="older-category", is_active=True)
        newer = Category.all_objects.create(name="Newer Category", slug="newer-category", is_active=True)

        older.sort_order = 0
        newer.sort_order = 99
        older.save(update_fields=["sort_order", "updated_at"])
        newer.save(update_fields=["sort_order", "updated_at"])

        sorted_response = self.client.get("/api/v1/catalog/categories/")
        self.assertEqual(sorted_response.status_code, status.HTTP_200_OK)
        sorted_names = [item["name"] for item in sorted_response.data["data"]]
        self.assertEqual(sorted_names[:2], [older.name, newer.name])

        latest_response = self.client.get("/api/v1/catalog/categories/?latest=true")
        self.assertEqual(latest_response.status_code, status.HTTP_200_OK)
        latest_names = [item["name"] for item in latest_response.data["data"]]
        self.assertEqual(latest_names[:2], [newer.name, older.name])
