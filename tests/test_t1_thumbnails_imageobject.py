"""Unit tests for T1: WP Featured Image thumbnails, PressAI Vision image descriptions, and ImageObject JSON-LD schema.

Test coverage:
  1. PressAI environment variable aliases in _describe_image_via_saas
  2. _upload_image_to_wp HTTP fallback via image_url
  3. set_youtube_thumbnail PressAI image_meta support
  4. build_schema_jsonld ImageObject generation (sources 1, 2, 3)
"""
import asyncio
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from core.injector import (
    _upload_image_to_wp,
    build_schema_jsonld,
    set_youtube_thumbnail,
)
from requests.auth import HTTPBasicAuth


class TestT1ThumbnailsAndImageObject(unittest.TestCase):
    """Test suite for T1 implementation."""

    def test_describe_image_via_saas_aliases(self):
        """Verify _describe_image_via_saas recognizes PRESSAI_API_URL and PRESSAI_EXTERNAL_TOKEN."""
        from api.services.pipeline import _describe_image_via_saas

        env_patch = {
            "PRESSAI_API_URL": "https://pressai.test",
            "PRESSAI_EXTERNAL_TOKEN": "secret-pressai-token",
            "SAAS_API_URL": "",
            "EXTERNAL_API_TOKEN": "",
            "SAAS_API_TOKEN": "",
        }
        with patch.dict(os.environ, env_patch):
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                mock_resp.json.return_value = {
                    "ok": True,
                    "descriptions": {
                        "alt_text": "Kadr wideo: test",
                        "title": "Tytuł miniatury",
                        "caption": "Podpis",
                        "description": "Szczegółowy opis",
                        "filename": "test-kadr.jpg",
                    },
                }
                mock_post.return_value = mock_resp

                res = asyncio.run(_describe_image_via_saas(
                    image_url="https://img.youtube.com/vi/test123/maxresdefault.jpg",
                    article_title="Testowy artykuł",
                    focus_keywords=["kadr wideo", "seo"],
                    site_brand="Prawy",
                ))

                self.assertIsNotNone(res)
                self.assertEqual(res.get("alt_text"), "Kadr wideo: test")
                self.assertEqual(res.get("filename"), "test-kadr.jpg")

                called_url = mock_post.call_args[0][0]
                self.assertEqual(called_url, "https://pressai.test/api/external/describe-image")
                called_headers = mock_post.call_args[1].get("headers", {})
                self.assertEqual(called_headers.get("Authorization"), "Bearer secret-pressai-token")

                called_payload = mock_post.call_args[1].get("json", {})
                self.assertEqual(called_payload.get("image_url"), "https://img.youtube.com/vi/test123/maxresdefault.jpg")
                self.assertEqual(called_payload.get("context", {}).get("article_title"), "Testowy artykuł")
                self.assertIn("kadr wideo", called_payload.get("context", {}).get("focus_keywords", []))

    def test_upload_image_to_wp_via_http_url(self):
        """Verify _upload_image_to_wp falls back to downloading image_url when image_path is missing."""
        descriptions = {
            "filename": "custom-seo-name.jpg",
            "alt_text": "Testowy Alt",
            "title": "Testowy Tytuł",
            "caption": "Testowy Podpis",
            "description": "Testowy Pełny Opis",
        }

        fake_image_bytes = b"\xff\xd8\xff\xe0" + b"0" * 2000

        with patch("requests.get") as mock_get, patch("requests.post") as mock_post:
            mock_dl_resp = MagicMock()
            mock_dl_resp.status_code = 200
            mock_dl_resp.content = fake_image_bytes
            mock_get.return_value = mock_dl_resp

            mock_upload_resp = MagicMock()
            mock_upload_resp.status_code = 201
            mock_upload_resp.json.return_value = {
                "id": 4321,
                "source_url": "https://portal.test/wp-content/uploads/custom-seo-name.jpg",
                "media_details": {"width": 1280, "height": 720},
            }

            mock_patch_resp = MagicMock()
            mock_patch_resp.status_code = 200
            mock_patch_resp.json.return_value = {"id": 4321}

            mock_post.side_effect = [mock_upload_resp, mock_patch_resp]

            res = _upload_image_to_wp(
                image_path="/nonexistent/temp/path/img.jpg",
                descriptions=descriptions,
                wp_base_url="https://portal.test",
                wp_user="admin",
                wp_app_password="pwd",
                image_url="https://cdn.test/remote-img.jpg",
            )

            self.assertIsNotNone(res)
            self.assertEqual(res["id"], 4321)
            self.assertEqual(res["url"], "https://portal.test/wp-content/uploads/custom-seo-name.jpg")
            self.assertEqual(res["width"], 1280)
            self.assertEqual(res["height"], 720)

            mock_get.assert_called_once_with("https://cdn.test/remote-img.jpg", timeout=20)

            upload_call = mock_post.call_args_list[0]
            self.assertIn("custom-seo-name.jpg", upload_call[1]["headers"]["Content-Disposition"])

            patch_call = mock_post.call_args_list[1]
            self.assertEqual(patch_call[1]["json"]["alt_text"], "Testowy Alt")
            self.assertEqual(patch_call[1]["json"]["caption"], "Testowy Podpis")
            self.assertEqual(patch_call[1]["json"]["description"], "Testowy Pełny Opis")

    def test_set_youtube_thumbnail_image_meta(self):
        """Verify set_youtube_thumbnail uses PressAI image_meta."""
        auth = HTTPBasicAuth("admin", "pwd")
        image_meta = {
            "filename": "pressai-thumb.jpg",
            "alt_text": "PressAI Miniatura Alt",
            "title": "PressAI Miniatura Tytuł",
            "caption": "PressAI Podpis",
            "description": "PressAI Opis",
        }

        fake_thumb = b"\xff\xd8\xff\xe0" + b"x" * 6000

        with patch("requests.get") as mock_get, patch("requests.post") as mock_post:
            mock_dl = MagicMock()
            mock_dl.status_code = 200
            mock_dl.content = fake_thumb

            mock_search = MagicMock()
            mock_search.status_code = 200
            mock_search.json.return_value = []

            mock_get.side_effect = [mock_dl, mock_search]

            mock_upload = MagicMock()
            mock_upload.status_code = 201
            mock_upload.json.return_value = {"id": 999}

            mock_set_post = MagicMock()
            mock_set_post.status_code = 200

            mock_patch = MagicMock()
            mock_patch.status_code = 200

            mock_post.side_effect = [mock_upload, mock_set_post, mock_patch]

            media_id = set_youtube_thumbnail(
                wp_id=10,
                yt_id="abc12345",
                post_title="Mój Post",
                wp_base_url="https://prawy.pl",
                auth=auth,
                image_meta=image_meta,
            )

            self.assertEqual(media_id, 999)
            patch_call = mock_post.call_args_list[2]
            self.assertEqual(patch_call[1]["json"]["alt_text"], "PressAI Miniatura Alt")
            self.assertEqual(patch_call[1]["json"]["title"], "PressAI Miniatura Tytuł")
            self.assertEqual(patch_call[1]["json"]["caption"], "PressAI Podpis")

    def test_build_schema_jsonld_imageobject(self):
        """Verify build_schema_jsonld produces valid @type: ImageObject for all fallback cases."""
        # Case 1: uploaded_images from WP Media Library
        seo_1 = {
            "seo_title": "Wideo Test 1",
            "video_description": "Opis wideo 1",
            "total_duration": 120,
            "uploaded_images": [
                {
                    "wp_url": "https://portal.test/wp-content/uploads/img1.jpg",
                    "width": 1280,
                    "height": 720,
                    "title": "Zrzut 1",
                    "caption": "Podpis 1",
                }
            ],
        }
        schemas_1 = build_schema_jsonld(seo_1, "yt111", "2026-10-24T20:00:00+00:00")
        video_obj_1 = schemas_1[0]
        self.assertIn("image", video_obj_1)
        self.assertEqual(len(video_obj_1["image"]), 1)
        self.assertEqual(video_obj_1["image"][0]["@type"], "ImageObject")
        self.assertEqual(video_obj_1["image"][0]["url"], "https://portal.test/wp-content/uploads/img1.jpg")
        self.assertEqual(video_obj_1["image"][0]["name"], "Zrzut 1")

        # Case 2: fallback to image_data
        seo_2 = {
            "seo_title": "Wideo Test 2",
            "video_description": "Opis wideo 2",
            "total_duration": 120,
            "image_data": [
                {
                    "url": "https://pressai.test/img/screenshot.jpg",
                    "descriptions": {
                        "title": "Tytuł z PressAI",
                        "caption": "Podpis z PressAI",
                    },
                }
            ],
        }
        schemas_2 = build_schema_jsonld(seo_2, "yt222", "2026-10-24T20:00:00+00:00")
        video_obj_2 = schemas_2[0]
        self.assertIn("image", video_obj_2)
        self.assertEqual(video_obj_2["image"][0]["@type"], "ImageObject")
        self.assertEqual(video_obj_2["image"][0]["url"], "https://pressai.test/img/screenshot.jpg")
        self.assertEqual(video_obj_2["image"][0]["name"], "Tytuł z PressAI")

        # Case 3: fallback to YouTube thumbnail
        seo_3 = {
            "seo_title": "Wideo Test 3",
            "video_description": "Opis wideo 3",
            "total_duration": 120,
            "thumbnail_url": "https://img.youtube.com/vi/yt333/maxresdefault.jpg",
        }
        schemas_3 = build_schema_jsonld(seo_3, "yt333", "2026-10-24T20:00:00+00:00")
        video_obj_3 = schemas_3[0]
        self.assertIn("image", video_obj_3)
        self.assertEqual(video_obj_3["image"][0]["@type"], "ImageObject")
        self.assertEqual(video_obj_3["image"][0]["url"], "https://img.youtube.com/vi/yt333/maxresdefault.jpg")
        self.assertEqual(video_obj_3["image"][0]["width"], 1280)
        self.assertEqual(video_obj_3["image"][0]["height"], 720)


if __name__ == "__main__":
    unittest.main()
