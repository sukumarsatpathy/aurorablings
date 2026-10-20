"""
Product video: one short clip per product, uploaded by staff, shown on the
product page.

What matters: only staff can upload, only real MP4/WebM files are accepted
(by content, not by name), the size cap holds, replacing or removing a video
deletes the old file, and the product detail exposes the URL.
"""
import os
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User, UserRole
from apps.catalog.models import Category, Product
from core import media as core_media

MP4_HEAD = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom"
WEBM_HEAD = b"\x1a\x45\xdf\xa3" + b"\x00" * 28


def _video(name="clip.mp4", head=MP4_HEAD, size=2048):
    return SimpleUploadedFile(name, head + b"\x00" * (size - len(head)), content_type="video/mp4")


class ProductVideoTests(APITestCase):
    def setUp(self):
        self._tmp_media = tempfile.mkdtemp(prefix="aurora-video-tests-")
        override = override_settings(MEDIA_ROOT=self._tmp_media)
        override.enable()
        self.addCleanup(override.disable)
        self.addCleanup(lambda: shutil.rmtree(self._tmp_media, ignore_errors=True))

        category = Category.all_objects.create(name="Bangles", slug="bangles", is_active=True)
        self.product = Product.all_objects.create(name="Laal Noor", slug="laal-noor", category=category, is_active=True)
        self.staff = User.objects.create_user(email="staff@example.com", password="Secret123", role=UserRole.STAFF)
        self.customer = User.objects.create_user(email="c@example.com", password="Secret123", role=UserRole.CUSTOMER)
        self.url = f"/api/v1/catalog/products/{self.product.id}/video/"

    def _upload(self, file):
        self.client.force_authenticate(self.staff)
        return self.client.post(self.url, {"video": file}, format="multipart")

    def test_staff_can_upload_mp4_and_detail_shows_it(self):
        response = self._upload(_video())
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.product.refresh_from_db()
        self.assertTrue(self.product.video.name.endswith(".mp4"))
        self.assertNotIn("clip", self.product.video.name)  # random safe name

        detail = self.client.get(f"/api/v1/catalog/products/slug/{self.product.slug}/").json()["data"]
        self.assertTrue(detail["video"].endswith(".mp4"))

    def test_webm_is_accepted(self):
        response = self._upload(_video("clip.webm", head=WEBM_HEAD))
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

    def test_non_video_is_rejected_even_with_video_name(self):
        response = self._upload(_video("evil.mp4", head=b"<?php echo 1; ?>"))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.product.refresh_from_db()
        self.assertFalse(self.product.video)

    def test_size_cap(self):
        response = self._upload(_video(size=core_media.MAX_VIDEO_UPLOAD_BYTES + 1))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_customers_and_anonymous_cannot_upload(self):
        anon = self.client.post(self.url, {"video": _video()}, format="multipart")
        self.assertIn(anon.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))
        self.client.force_authenticate(self.customer)
        response = self.client.post(self.url, {"video": _video()}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_replace_and_remove_delete_old_files(self):
        self._upload(_video())
        self.product.refresh_from_db()
        first_path = self.product.video.path
        self._upload(_video("second.mp4"))
        self.product.refresh_from_db()
        self.assertFalse(os.path.exists(first_path))
        second_path = self.product.video.path
        self.assertTrue(os.path.exists(second_path))

        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.product.refresh_from_db()
        self.assertFalse(self.product.video)
        self.assertFalse(os.path.exists(second_path))
