"""Tests for core/injector.py — title-sync deliverable (DISPATCH-VSE-DEV-01-20260520).

Tests: _sanitize_slug(), update_post payload (title+slug), slug explicit enforcement.
"""
import sys
sys.path.insert(0, "/home/tobroz/projects/video-seo-engine")

import pytest
from unittest.mock import MagicMock, patch

from core.injector import _sanitize_slug


# ---------------------------------------------------------------------------
# _sanitize_slug tests
# ---------------------------------------------------------------------------

class TestSanitizeSlug:

    def test_polish_chars_transliterated(self):
        slug = _sanitize_slug("Zmiany w polskiej polityce")
        assert "ó" not in slug and "ą" not in slug and "ę" not in slug

    def test_lowercase_only(self):
        slug = _sanitize_slug("Polityka POLSKA Zmiany")
        assert slug == slug.lower()

    def test_no_spaces(self):
        slug = _sanitize_slug("polityka polska zmiany")
        assert " " not in slug

    def test_stop_words_removed(self):
        slug = _sanitize_slug("i w z na do polityka")
        tokens = slug.split("-")
        for sw in ["i", "w", "z", "na", "do"]:
            assert sw not in tokens, f"Stop-word '{sw}' in slug: {slug!r}"

    def test_max_length_60(self):
        long_text = "bardzo długi tytuł artykułu który zawiera wiele słów kluczowych polityka polska"
        slug = _sanitize_slug(long_text)
        assert len(slug) <= 60

    def test_special_chars_stripped(self):
        slug = _sanitize_slug("Polityka! Polska? 2026.")
        assert "!" not in slug and "?" not in slug and "." not in slug

    def test_consecutive_hyphens_collapsed(self):
        slug = _sanitize_slug("polityka  polska")
        assert "--" not in slug

    def test_no_leading_trailing_hyphens(self):
        slug = _sanitize_slug("  polityka polska  ")
        assert not slug.startswith("-") and not slug.endswith("-")

    def test_empty_string(self):
        assert _sanitize_slug("") == ""

    def test_full_polish_sentence_url_safe(self):
        slug = _sanitize_slug("Zmiany w polskiej polityce co się zmienia w 2026")
        assert " " not in slug
        assert len(slug) <= 60
        polish = set("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ")
        assert not any(c in polish for c in slug)


# ---------------------------------------------------------------------------
# update_post payload tests
# ---------------------------------------------------------------------------

def _make_seo(**kw) -> dict:
    base = {
        "focus_keyphrase": "polityka polska",
        "post_title": "Polityka polska 2026",
        "seo_title": "Polityka 2026 | Prawy TV",
        "yt_title": "Co się zmienia w Polsce?",
        "wp_slug": "polityka-polska-2026",
        "meta_description": "Opis.",
        "lead": "<p>Lead.</p>",
        "article_body": "<p>Treść.</p>",
        "quotes": [], "chapters": [], "faq": [],
        "youtube_description": "YT", "video_description": "vid",
        "tags": ["polityka"], "total_duration": 600, "duration_iso": "PT10M0S",
    }
    base.update(kw)
    return base


class TestUpdatePostPayload:

    def _run(self, seo):
        """Run update_post with mocked requests, return captured POST payload."""
        from core import injector
        from requests.auth import HTTPBasicAuth

        auth = HTTPBasicAuth("user", "pass")
        captured = {}

        def fake_get(url, **kwargs):
            m = MagicMock()
            m.status_code = 200
            m.json.return_value = {"date": "2026-01-15T10:00:00", "link": "https://prawy.pl/test/"}
            return m

        def fake_post(url, json=None, **kwargs):
            if json:
                captured.update(json)
            m = MagicMock()
            m.status_code = 200
            m.json.return_value = {"link": "https://prawy.pl/test/"}
            return m

        with patch("core.injector.requests.get", side_effect=fake_get), \
             patch("core.injector.requests.post", side_effect=fake_post):
            injector.update_post(
                wp_id=123, seo=seo, yt_id="TEST123",
                wp_base_url="https://prawy.pl", auth=auth,
            )
        return captured

    def test_payload_has_title_when_post_title_given(self):
        payload = self._run(_make_seo())
        assert "title" in payload
        assert payload["title"] == "Polityka polska 2026"

    def test_payload_has_slug_from_gemini(self):
        payload = self._run(_make_seo())
        assert "slug" in payload
        assert payload["slug"] == "polityka-polska-2026"

    def test_slug_explicit_even_when_wp_slug_empty(self):
        """When wp_slug empty, slug derived from post_title must still be in payload."""
        payload = self._run(_make_seo(wp_slug=""))
        assert "slug" in payload
        slug = payload["slug"]
        assert " " not in slug and slug == slug.lower()

    def test_no_title_when_post_title_missing(self):
        payload = self._run(_make_seo(post_title="", wp_slug=""))
        assert "title" not in payload

    def test_no_slug_when_both_empty(self):
        payload = self._run(_make_seo(post_title="", wp_slug=""))
        assert "slug" not in payload
