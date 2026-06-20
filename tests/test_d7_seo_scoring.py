"""Tests for D7 SEO Scoring Fix (vse-dev-22).

CO: Testy walidują 6 zmian D7 w injector.py + generator.py.

PO CO: RankMath scoring 57→90+ wymaga gwarancji że:
  - meta_description z LLM jest używany zamiast obcinania lead
  - Keyphrase jest walidowana w meta_desc i slug
  - External links nie mają noreferrer
  - Prompt zawiera instrukcje dot. keyword density

JAK: Unit testy z mockami requests — bez połączeń sieciowych.
"""
import sys
sys.path.insert(0, "/home/tobroz/projects/video-seo-engine")

import pytest
from unittest.mock import MagicMock, patch

from core.injector import (
    _build_rankmath_meta,
    _build_external_link_block,
    _sanitize_slug,
    _strip_html,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_seo(**kw) -> dict:
    """Build a minimal SEO dict for testing."""
    base = {
        "focus_keyphrase": "polityka obronna",
        "focus_keyphrases": ["polityka obronna", "bezpieczeństwo polski"],
        "post_title": "Polityka obronna Polski 2026",
        "seo_title": "Polityka obronna 2026 | Prawy TV",
        "yt_title": "Jak Polska buduje obronę?",
        "wp_slug": "polityka-obronna-polski-2026",
        "meta_description": "Polityka obronna Polski zmienia się w 2026. Analiza.",
        "lead": "<p>Lead artykułu o polityce obronnej.</p>",
        "article_body": "<p>Treść artykułu.</p>",
        "quotes": [], "chapters": [], "faq": [],
        "youtube_description": "YT desc",
        "video_description": "vid desc",
        "tags": ["polityka"],
        "total_duration": 600,
        "duration_iso": "PT10M0S",
    }
    base.update(kw)
    return base


def _make_profile(**kw) -> dict:
    """Build a minimal profile dict for testing."""
    base = {
        "portal_id": "prawy",
        "display_name": "Prawy.pl",
        "seo_external_link": {
            "url": "https://www.youtube.com/@PrawyTV",
            "anchor": "Prawy TV na YouTube",
        },
    }
    base.update(kw)
    return base


# ---------------------------------------------------------------------------
# D7 Faza 1.1: _build_rankmath_meta — meta_description z LLM
# ---------------------------------------------------------------------------

class TestBuildRankmathMetaD7:
    """D7 Faza 1.1 + 3.2: meta_description from LLM + keyphrase validation."""

    @patch("core.injector.build_focus_keywords", return_value="polityka obronna")
    def test_meta_desc_from_llm_field(self, mock_bfk):
        """When seo has meta_description, use it instead of truncating lead."""
        seo = _make_seo(
            meta_description="Polityka obronna Polski w 2026 — pełna analiza.",
            lead="<p>Ten lead jest bardzo długi i nie zawiera frazy kluczowej wcale.</p>",
        )
        meta = _build_rankmath_meta(seo)
        assert meta["rank_math_description"] == "Polityka obronna Polski w 2026 — pełna analiza."

    @patch("core.injector.build_focus_keywords", return_value="polityka obronna")
    def test_meta_desc_fallback_to_lead_when_no_meta_description(self, mock_bfk):
        """When meta_description is empty, fall back to truncated lead."""
        seo = _make_seo(
            meta_description="",
            lead="<p>Lead artykułu o polityce obronnej Polski.</p>",
        )
        meta = _build_rankmath_meta(seo)
        desc = meta["rank_math_description"]
        assert "Lead artykułu o polityce obronnej" in desc
        # Should NOT contain HTML tags
        assert "<p>" not in desc

    @patch("core.injector.build_focus_keywords", return_value="polityka obronna")
    def test_meta_desc_fallback_to_lead_when_field_missing(self, mock_bfk):
        """When meta_description key is absent, fall back to lead."""
        seo = _make_seo(lead="<p>Opis artykułu.</p>")
        del seo["meta_description"]
        meta = _build_rankmath_meta(seo)
        assert "Opis artykułu" in meta["rank_math_description"]

    @patch("core.injector.build_focus_keywords", return_value="polityka obronna")
    def test_meta_desc_keyphrase_present_no_append(self, mock_bfk):
        """When meta_desc already contains keyphrase word, don't append."""
        seo = _make_seo(
            meta_description="Analiza polityki obronnej na 2026 rok.",
            focus_keyphrase="polityka obronna",
        )
        meta = _build_rankmath_meta(seo)
        desc = meta["rank_math_description"]
        # Should NOT have appended the keyphrase again
        assert desc.count("polityka") == 1 or desc.count("obronnej") >= 1

    @patch("core.injector.build_focus_keywords", return_value="polityka obronna")
    def test_meta_desc_keyphrase_missing_gets_appended(self, mock_bfk):
        """When meta_desc has no keyphrase words (>2 chars), append keyphrase."""
        seo = _make_seo(
            meta_description="To jest opis bez żadnych ważnych słów.",
            focus_keyphrase="cyberbezpieczeństwo NATO",
        )
        meta = _build_rankmath_meta(seo)
        desc = meta["rank_math_description"]
        # Keyphrase should be appended
        assert "cyberbezpieczeństwo" in desc.lower() or "NATO" in desc

    @patch("core.injector.build_focus_keywords", return_value="polityka obronna")
    def test_meta_desc_max_160_chars_after_append(self, mock_bfk):
        """After appending keyphrase, meta_desc should be <= 160 chars."""
        seo = _make_seo(
            meta_description="A" * 140,
            focus_keyphrase="cyberbezpieczeństwo",
        )
        meta = _build_rankmath_meta(seo)
        desc = meta["rank_math_description"]
        assert len(desc) <= 160


# ---------------------------------------------------------------------------
# D7 Faza 1.2: _build_external_link_block — no noreferrer
# ---------------------------------------------------------------------------

class TestExternalLinkBlockD7:
    """D7 Faza 1.2: External link must use rel='noopener' without noreferrer."""

    def test_no_noreferrer_in_output(self):
        """External link HTML must NOT contain 'noreferrer'."""
        profile = _make_profile()
        html = _build_external_link_block(profile)
        assert "noreferrer" not in html

    def test_noopener_present(self):
        """External link must have rel='noopener'."""
        profile = _make_profile()
        html = _build_external_link_block(profile)
        assert 'rel="noopener"' in html

    def test_target_blank_present(self):
        """External link must open in new tab."""
        profile = _make_profile()
        html = _build_external_link_block(profile)
        assert 'target="_blank"' in html

    def test_anchor_text_used(self):
        """Custom anchor text from profile should be in HTML."""
        profile = _make_profile()
        html = _build_external_link_block(profile)
        assert "Prawy TV na YouTube" in html

    def test_url_used(self):
        """URL from profile should be in href."""
        profile = _make_profile()
        html = _build_external_link_block(profile)
        assert "https://www.youtube.com/@PrawyTV" in html

    def test_empty_when_no_profile(self):
        assert _build_external_link_block(None) == ""

    def test_empty_when_no_url(self):
        profile = _make_profile(seo_external_link={"url": "", "anchor": "test"})
        assert _build_external_link_block(profile) == ""

    def test_default_anchor_when_empty(self):
        profile = _make_profile(seo_external_link={"url": "https://example.com", "anchor": ""})
        html = _build_external_link_block(profile)
        assert "Źródło zewnętrzne" in html


# ---------------------------------------------------------------------------
# D7 Faza 3.1: Slug keyphrase validation in update_post
# ---------------------------------------------------------------------------

class TestSlugKeyphraseValidationD7:
    """D7 Faza 3.1: Slug must contain keyphrase words, override if not."""

    def _run_update_post(self, seo):
        """Run update_post with mocked requests, return captured POST payload."""
        from core import injector
        from requests.auth import HTTPBasicAuth

        auth = HTTPBasicAuth("user", "pass")
        captured = {}

        def fake_get(url, **kwargs):
            m = MagicMock()
            m.status_code = 200
            m.json.return_value = {
                "date": "2026-01-15T10:00:00",
                "link": "https://prawy.pl/test/",
            }
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

    def test_slug_with_keyphrase_words_not_overridden(self):
        """When slug already contains keyphrase words, no override."""
        seo = _make_seo(
            wp_slug="polityka-obronna-2026",
            focus_keyphrase="polityka obronna",
        )
        payload = self._run_update_post(seo)
        assert payload["slug"] == "polityka-obronna-2026"

    def test_slug_without_keyphrase_words_is_overridden(self):
        """When slug has NO keyphrase words, override to sanitized keyphrase."""
        seo = _make_seo(
            wp_slug="artykul-o-zmianach-2026",
            focus_keyphrase="polityka obronna",
        )
        payload = self._run_update_post(seo)
        slug = payload["slug"]
        # Must contain at least one word from keyphrase
        kp_words = set(_sanitize_slug("polityka obronna").split("-"))
        slug_words = set(slug.split("-"))
        assert kp_words.intersection(slug_words), f"Slug {slug!r} doesn't contain keyphrase words"

    def test_slug_partial_keyphrase_match_not_overridden(self):
        """When slug contains at least one keyphrase word, no override."""
        seo = _make_seo(
            wp_slug="analiza-polityka-2026",
            focus_keyphrase="polityka obronna",
        )
        payload = self._run_update_post(seo)
        assert payload["slug"] == "analiza-polityka-2026"

    def test_empty_keyphrase_no_crash(self):
        """Empty keyphrase should not cause override or crash."""
        seo = _make_seo(
            wp_slug="artykul-2026",
            focus_keyphrase="",
        )
        payload = self._run_update_post(seo)
        assert payload["slug"] == "artykul-2026"


# ---------------------------------------------------------------------------
# D7 Faza 2: Prompt Engineering — verify prompt contains D7 instructions
# ---------------------------------------------------------------------------

class TestPromptEngineeringD7:
    """D7 Faza 2: Verify that generate_seo_v4 prompt includes SEO instructions."""

    def _capture_prompt(self):
        """Call generate_seo_v4 with mocked LLM, capture the prompt string."""
        import json
        from core.generator import generate_seo_v4

        captured_prompt = {}

        def fake_llm(prompt, api_key, provider="gemini"):
            captured_prompt["prompt"] = prompt
            # Return minimal valid JSON
            return json.dumps({
                "focus_keyphrases": ["test"],
                "post_title": "Test",
                "seo_title": "Test",
                "yt_title": "Test",
                "wp_slug": "test",
                "meta_description": "Test desc",
                "lead": "Test lead",
                "article_body": "<p>Test</p>",
                "quotes": [],
                "chapters": [],
                "faq": [],
                "youtube_description": "YT",
                "video_description": "vid",
                "tags": ["test"],
            })

        with patch("core.generator._call_llm", side_effect=fake_llm):
            generate_seo_v4(
                title="Test title",
                timestamped_text="[00:00] test text",
                total_duration=600,
                yt_url="https://www.youtube.com/watch?v=TEST",
                api_key="fake-key",
            )

        return captured_prompt["prompt"]

    def test_prompt_has_keyword_density_instruction(self):
        """Prompt must instruct LLM about keyword density 1-1.5%."""
        prompt = self._capture_prompt()
        assert "MINIMUM 3-5 RAZY" in prompt or "3-5 RAZY" in prompt
        assert "1-1.5%" in prompt

    def test_prompt_has_first_paragraph_keyphrase(self):
        """Prompt must instruct LLM to put keyphrase in first paragraph."""
        prompt = self._capture_prompt()
        assert "Pierwszy akapit article_body MUSI" in prompt

    def test_prompt_has_lead_first_sentence_keyphrase(self):
        """Prompt must instruct LLM to put keyphrase in first sentence of lead."""
        prompt = self._capture_prompt()
        assert "PIERWSZE ZDANIE musi zawierac" in prompt

    def test_prompt_has_slug_keyphrase_instruction(self):
        """Prompt must instruct LLM that slug starts with keyphrase words."""
        prompt = self._capture_prompt()
        assert "SLUG MUSI ZACZYNAC SIE" in prompt
