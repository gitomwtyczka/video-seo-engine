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
from unittest.mock import MagicMock, AsyncMock, patch

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


class TestWatchingPageSinglePassAndCleanTranscript:

    def test_pass1_prompt_does_not_contain_clean_transcript(self):
        captured_prompts = []

        def mock_call(prompt, api_key, provider="gemini"):
            captured_prompts.append(prompt)
            return _make_seo_json()

        with patch("core.generator._call_llm", side_effect=mock_call):
            import core.generator as gen_mod
            gen_mod.generate_seo_v4(
                title="Test tytul",
                timestamped_text="[00:00] Tresc testowa.",
                total_duration=600.0,
                yt_url="https://www.youtube.com/watch?v=TEST123",
                api_key="FAKE_KEY",
                publication_type="watching_page",
            )
        assert len(captured_prompts) == 1
        prompt = captured_prompts[0]
        assert "clean_transcript" not in prompt, "Pass 1 prompt must not contain 'clean_transcript'"
        assert '"article_body":"<p>...</p><p>...</p>"' in prompt, "Pass 1 watching_page schema must contain article_body"

    def test_watching_page_single_pass_skips_pass2_when_article_body_ge_200(self, tmp_path):
        import core.generator as gen_mod
        vtt_file = tmp_path / "test.vtt"
        vtt_file.write_text("WEBVTT\n\n00:00:00.000 --> 00:00:10.000\n[00:00] Tresc testowa wideo z odpowiednio dlugim transkryptem powyzej piecdziesieciu znakow.\n", encoding="utf-8")

        long_body = "<p>" + ("Bardzo wazny akapit pierwszy z analizy materialu. " * 3) + "</p>"
        long_body += "<p>" + ("Kluczowy akapit drugi wyjasniajacy dlaczego warto obejrzec. " * 3) + "</p>"
        assert len(long_body) >= 200

        seo_json = _make_seo_json(article_body=long_body)

        with patch("core.generator._call_llm", return_value=seo_json), \
             patch("core.generator.generate_article_content", AsyncMock()) as mock_pass2:
            res = gen_mod.process_video(
                youtube_id="TEST123",
                wp_id=1,
                post_title="Tytul testowy",
                yt_url="https://www.youtube.com/watch?v=TEST123",
                vtt_path=str(vtt_file),
                api_key="FAKE_KEY",
                publication_type="watching_page",
            )
            assert mock_pass2.call_count == 0, "Pass 2 should NOT be called for watching_page when article_body >= 200"
            assert res["article_engine"] == "pass1_watching_page"
            assert res["article_body"] == long_body

    def test_clean_transcript_populated_from_build_clean_transcript_from_segments(self, tmp_path):
        import core.generator as gen_mod
        vtt_file = tmp_path / "test.vtt"
        vtt_file.write_text("WEBVTT\n\n00:00:00.000 --> 00:00:10.000\n[00:00] Yyy witamy panstwa eee w programie. Dzisiejszy odcinek poswiecony jest waznym sprawom gospodarczym.\n", encoding="utf-8")

        seo_json = _make_seo_json()

        with patch("core.generator._call_llm", return_value=seo_json), \
             patch("core.generator.generate_article_content", AsyncMock(return_value=("<p>Pass2</p>", "local_fallback"))):
            res = gen_mod.process_video(
                youtube_id="TEST123",
                wp_id=1,
                post_title="Tytul testowy",
                yt_url="https://www.youtube.com/watch?v=TEST123",
                vtt_path=str(vtt_file),
                api_key="FAKE_KEY",
                publication_type="full_analysis",
            )
            assert "clean_transcript" in res
            assert len(res["clean_transcript"]) > 0
            assert "[00:00]" in res["clean_transcript"]
            # Verify ASR fillers removed by build_clean_transcript_from_segments
            assert "Yyy" not in res["clean_transcript"]
            assert "eee" not in res["clean_transcript"]

    def test_claude_and_gemini_truncation_warning(self):
        import core.generator as gen_mod

        # Claude truncation detection
        with patch("anthropic.Anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_msg = MagicMock()
            mock_msg.stop_reason = "max_tokens"
            mock_msg.content = [MagicMock(text="Truncated Claude text")]
            mock_msg.usage = MagicMock(input_tokens=50, output_tokens=8192)
            mock_client.messages.create.return_value = mock_msg
            mock_anthropic.return_value = mock_client

            with patch.object(gen_mod.logger, "warning") as mock_warn:
                txt = gen_mod._call_llm("test", "key", provider="claude")
                assert txt == "Truncated Claude text"
                calls = [str(c) for c in mock_warn.call_args_list]
                assert any("LLM_TRUNCATED" in c and "provider=claude" in c for c in calls)

        # Gemini truncation detection
        with patch("google.genai.Client") as mock_genai_client:
            mock_client = MagicMock()
            mock_resp = MagicMock()
            mock_resp.text = "Truncated Gemini text"
            cand = MagicMock()
            cand.finish_reason = "MAX_TOKENS"
            mock_resp.candidates = [cand]
            mock_resp.usage_metadata = MagicMock(prompt_token_count=50, candidates_token_count=8192)
            mock_client.models.generate_content.return_value = mock_resp
            mock_genai_client.return_value = mock_client

            with patch.object(gen_mod.logger, "warning") as mock_warn:
                txt = gen_mod._call_llm("test", "key", provider="gemini")
                assert txt == "Truncated Gemini text"
                calls = [str(c) for c in mock_warn.call_args_list]
                assert any("LLM_TRUNCATED" in c and "provider=gemini" in c for c in calls)
