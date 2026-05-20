"""Tests for core/yt_admin.py — title-sync deliverable (DISPATCH-VSE-DEV-01-20260520).

Tests: update_video_title_and_description() — dry_run, truncation, fallback, errors.
"""
import sys
sys.path.insert(0, "/home/tobroz/projects/video-seo-engine")

import pytest
from unittest.mock import MagicMock, patch


def _seo(**kw) -> dict:
    base = {
        "focus_keyphrase": "polityka polska",
        "yt_title": "Czy Polska zmieni się w 2026? Zaskakujące fakty!",
        "post_title": "Polityka polska 2026",
        "seo_title": "Polityka 2026 | Prawy TV",
        "video_description": "Opis wideo.",
        "lead": "Lead artykułu.",
        "chapters": [], "faq": [], "tags": ["polityka"],
    }
    base.update(kw)
    return base


def _video_data(title="Oryginalny tytuł") -> dict:
    return {"snippet": {
        "title": title, "description": "Oryginalna treść.",
        "categoryId": "25", "defaultLanguage": "pl",
        "defaultAudioLanguage": "pl", "tags": ["tag1"],
    }}


class TestUpdateVideoTitleAndDescriptionDryRun:

    def test_dry_run_returns_true(self):
        from core import yt_admin
        with patch.object(yt_admin, "get_video_data", return_value=_video_data()), \
             patch("core.yt_admin.requests.put") as mock_put:
            result = yt_admin.update_video_title_and_description(
                "VID1", _seo(), "https://prawy.pl/art/", dry_run=True
            )
        assert result is True
        mock_put.assert_not_called()

    def test_dry_run_logs_dry_run_text(self, caplog):
        import logging
        from core import yt_admin
        with patch.object(yt_admin, "get_video_data", return_value=_video_data()), \
             patch("core.yt_admin.requests.put"), \
             caplog.at_level(logging.INFO, logger="core.yt_admin"):
            yt_admin.update_video_title_and_description(
                "VID1", _seo(), "https://prawy.pl/art/", dry_run=True
            )
        assert "DRY RUN" in caplog.text


class TestYtTitleTruncation:

    def test_yt_title_truncated_at_100(self):
        seo = _seo(yt_title="A" * 120)
        captured = {}

        def fake_put(url, headers=None, json=None, **kwargs):
            captured.update(json or {})
            m = MagicMock(); m.status_code = 200; return m

        from core import yt_admin
        with patch.object(yt_admin, "get_video_data", return_value=_video_data()), \
             patch.object(yt_admin, "_auth_headers", return_value={}), \
             patch("core.yt_admin.requests.put", side_effect=fake_put):
            yt_admin.update_video_title_and_description("VID1", seo, "https://prawy.pl/", dry_run=False)

        sent = captured.get("snippet", {}).get("title", "")
        assert len(sent) <= 100
        assert sent == "A" * 100

    def test_yt_title_100_chars_not_modified(self):
        seo = _seo(yt_title="B" * 100)
        captured = {}

        def fake_put(url, headers=None, json=None, **kwargs):
            captured.update(json or {})
            m = MagicMock(); m.status_code = 200; return m

        from core import yt_admin
        with patch.object(yt_admin, "get_video_data", return_value=_video_data()), \
             patch.object(yt_admin, "_auth_headers", return_value={}), \
             patch("core.yt_admin.requests.put", side_effect=fake_put):
            yt_admin.update_video_title_and_description("VID2", seo, "https://prawy.pl/", dry_run=False)

        sent = captured.get("snippet", {}).get("title", "")
        assert sent == "B" * 100


class TestYtTitleFallback:

    def test_missing_yt_title_uses_existing(self):
        seo = _seo()
        del seo["yt_title"]
        existing = "Stary tytuł na YouTube"
        captured = {}

        def fake_put(url, headers=None, json=None, **kwargs):
            captured.update(json or {})
            m = MagicMock(); m.status_code = 200; return m

        from core import yt_admin
        with patch.object(yt_admin, "get_video_data", return_value=_video_data(existing)), \
             patch.object(yt_admin, "_auth_headers", return_value={}), \
             patch("core.yt_admin.requests.put", side_effect=fake_put):
            yt_admin.update_video_title_and_description("VID3", seo, "https://prawy.pl/", dry_run=False)

        assert captured.get("snippet", {}).get("title") == existing

    def test_api_403_returns_false(self):
        from core import yt_admin
        mock_resp = MagicMock(); mock_resp.status_code = 403; mock_resp.text = "Forbidden"
        with patch.object(yt_admin, "get_video_data", return_value=_video_data()), \
             patch.object(yt_admin, "_auth_headers", return_value={}), \
             patch("core.yt_admin.requests.put", return_value=mock_resp):
            result = yt_admin.update_video_title_and_description("VID4", _seo(), "https://prawy.pl/", dry_run=False)
        assert result is False

    def test_get_video_data_exception_returns_false(self):
        from core import yt_admin
        with patch.object(yt_admin, "get_video_data", side_effect=ValueError("not found")):
            result = yt_admin.update_video_title_and_description("VID5", _seo(), "https://prawy.pl/", dry_run=False)
        assert result is False
