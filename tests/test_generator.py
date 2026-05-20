"""Tests for core/generator.py — title-sync deliverable (DISPATCH-VSE-DEV-01-20260520).

Tests cover new output schema fields: post_title, yt_title, wp_slug.
Gemini API is mocked via sys.modules — no real API calls made.
genai is imported inline inside generate_seo_v4(), so we mock 'google.genai'
in sys.modules before the call.
"""
import json
import sys
import types
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, "/home/tobroz/projects/video-seo-engine")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_seo_json(**overrides) -> str:
    base = {
        "focus_keyphrase": "polityka polska",
        "post_title": "Polityka polska 2026 — co sie zmienia w Polsce",
        "seo_title": "Polityka polska 2026 | Prawy TV",
        "yt_title": "Czy Polska zmieni sie w 2026? Zaskakujace fakty!",
        "wp_slug": "polityka-polska-2026-co-sie-zmienia",
        "meta_description": "Informacje o polityce polskiej.",
        "lead": "W Polsce dzieje sie wiele.",
        "article_body": "<p>Artykul.</p>",
        "quotes": [{"text": "Cos.", "speaker": "Jan", "anchor_text": "cos waznego"}],
        "chapters": [{"label": "Wstep", "anchor_text": "na poczatku"}],
        "faq": [{"question": "Co?", "answer": "To..."}],
        "youtube_description": "Opis #PrawyTV",
        "video_description": "Opis wideo.",
        "tags": ["polityka", "polska"],
    }
    base.update(overrides)
    return json.dumps(base)


def _call_generate(json_str: str) -> dict:
    """Call generate_seo_v4 with fully mocked google.genai in sys.modules."""
    # Build mock genai module
    mock_genai = MagicMock()
    mock_client_instance = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = json_str
    mock_client_instance.models.generate_content.return_value = mock_resp
    mock_genai.Client.return_value = mock_client_instance

    # Build mock google package with genai attribute
    mock_google = types.ModuleType("google")
    mock_google.genai = mock_genai

    with patch.dict(sys.modules, {"google": mock_google, "google.genai": mock_genai}):
        # Reimport to pick up mocked modules
        import importlib
        import core.generator as gen_mod
        importlib.reload(gen_mod)

        result = gen_mod.generate_seo_v4(
            title="Test tytul",
            timestamped_text="[00:00] Tresc testowa.",
            total_duration=600.0,
            yt_url="https://www.youtube.com/watch?v=TEST123",
            api_key="FAKE_KEY",
        )
    return result


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGenerateSeoV4OutputSchema:

    def test_output_schema_has_post_title(self):
        result = _call_generate(_make_seo_json())
        assert "post_title" in result, "Missing field: post_title"

    def test_output_schema_has_yt_title(self):
        result = _call_generate(_make_seo_json())
        assert "yt_title" in result, "Missing field: yt_title"

    def test_output_schema_has_wp_slug(self):
        result = _call_generate(_make_seo_json())
        assert "wp_slug" in result, "Missing field: wp_slug"

    def test_post_title_contains_keyphrase(self):
        result = _call_generate(_make_seo_json())
        keyphrase = result.get("focus_keyphrase", "").lower()
        post_title = result.get("post_title", "").lower()
        assert keyphrase
        assert keyphrase in post_title, (
            f"post_title {post_title!r} does not contain keyphrase {keyphrase!r}"
        )

    def test_yt_title_max_100(self):
        result = _call_generate(_make_seo_json())
        yt_title = result.get("yt_title", "")
        assert len(yt_title) <= 100, f"yt_title too long: {len(yt_title)}"

    def test_wp_slug_no_spaces(self):
        result = _call_generate(_make_seo_json())
        assert " " not in result.get("wp_slug", "")

    def test_wp_slug_lowercase(self):
        result = _call_generate(_make_seo_json())
        slug = result.get("wp_slug", "")
        assert slug == slug.lower()

    def test_wp_slug_no_polish_chars(self):
        result = _call_generate(_make_seo_json())
        slug = result.get("wp_slug", "")
        polish = set("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ")
        found = [c for c in slug if c in polish]
        assert not found, f"Polish chars in slug: {found}"

    def test_existing_fields_preserved(self):
        required = [
            "focus_keyphrase", "seo_title", "meta_description", "lead",
            "article_body", "quotes", "chapters", "faq",
            "youtube_description", "video_description", "tags",
        ]
        result = _call_generate(_make_seo_json())
        for field in required:
            assert field in result, f"Pre-existing field missing: {field}"
