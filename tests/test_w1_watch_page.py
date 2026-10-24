\"\"\"Unit tests for W1 Watch Page Post Format & SEO Enhancements (TASK-01 to TASK-06).

Covering:
- TASK-01: WP post format 'video' vs 'standard'
- TASK-02: update_post & inject_video format payload
- TASK-03: responsive iframe embed inline styles
- TASK-04: VideoObject SeekToAction, @id, Article and BreadcrumbList schemas
- TASK-05: watching_page content length, H3 headings, and single-pass skip
- TASK-06: internal links deterministic fallback box
\"\"\"
import json
from unittest.mock import MagicMock, patch

import pytest
from requests.auth import HTTPBasicAuth

from core.generator import (
    _get_publication_type_override,
    generate_seo_v4,
)
from core.injector import (
    _build_internal_links_block,
    build_post_content,
    build_schema_jsonld,
    build_wp_article_sections,
    inject_video,
    update_post,
)


# ---------------------------------------------------------------------------
# Fixtures & Helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_seo_data():
    return {
        \"focus_keyphrase\": \"optymalizacja video seo\",
        \"post_title\": \"Jak optymalizować wideo pod YouTube i Google 2026\",
        \"seo_title\": \"Video SEO 2026 | Poradnik\",
        \"video_description\": \"Kompleksowy przewodnik po Video SEO.\",
        \"meta_description\": \"Dowiedz się jak optymalizować wideo pod wyszukiwarki.\",
        \"lead\": \"Optymalizacja wideo to kluczowy element strategii content marketingu.\",
        \"article_body\": \"<p>Akapit pierwszy wprowadzający w tematykę wideo marketingu.</p><p>Kolejny akapit szczegółowy.</p>\",
        \"chapters\": [
            {\"time\": 0, \"label\": \"Wstęp do Video SEO\"},
            {\"time\": 120, \"label\": \"Architektura schema.org\"},
        ],
        \"quotes\": [
            {\"speaker\": \"Jan Kowalski\", \"text\": \"Format video to przyszłość stron wideo.\", \"time\": 45}
        ],
        \"faq\": [
            {\"question\": \"Czym jest VideoObject?\", \"answer\": \"To schema dla Google.\"}
        ],
        \"post_url\": \"https://vse.impresjapr.pl/artykul-video-seo/\",
        \"yt_url\": \"https://www.youtube.com/watch?v=TEST_VID_123\",
        \"total_duration\": 360,
    }


# ---------------------------------------------------------------------------
# TASK-02: update_post & inject_video payload post_format
# ---------------------------------------------------------------------------

class TestTask02PostFormatPayload:

    @patch(\"requests.post\")
    @patch(\"core.injector.get_post_date\", return_value=\"2026-10-24T12:00:00+02:00\")
    def test_update_post_sends_format_video(self, mock_date, mock_post, sample_seo_data):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {\"link\": \"https://vse.impresjapr.pl/test-link\"}
        mock_post.return_value = mock_resp

        status, link = update_post(
            wp_id=123,
            seo=sample_seo_data,
            yt_id=\"TEST_VID_123\",
            wp_base_url=\"https://vse.impresjapr.pl\",
            auth=HTTPBasicAuth(\"user\", \"pass\"),
            post_format=\"video\",
        )

        assert status == 200
        assert mock_post.called
        # Check payload format
        args, kwargs = mock_post.call_args
        payload = kwargs.get(\"json\", {})
        assert payload.get(\"format\") == \"video\"

    @patch(\"requests.post\")
    @patch(\"core.injector.get_post_date\", return_value=\"2026-10-24T12:00:00+02:00\")
    def test_update_post_normalizes_standard_to_video(self, mock_date, mock_post, sample_seo_data):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {\"link\": \"https://vse.impresjapr.pl/test-link\"}
        mock_post.return_value = mock_resp

        update_post(
            wp_id=123,
            seo=sample_seo_data,
            yt_id=\"TEST_VID_123\",
            wp_base_url=\"https://vse.impresjapr.pl\",
            auth=HTTPBasicAuth(\"user\", \"pass\"),
            post_format=\"standard\",
        )

        args, kwargs = mock_post.call_args
        payload = kwargs.get(\"json\", {})
        assert payload.get(\"format\") == \"video\"

    @patch(\"core.injector.update_post\", return_value=(200, \"https://vse.impresjapr.pl/post\"))
    @patch(\"core.injector.update_rankmath_meta\", return_value=True)
    def test_inject_video_passes_post_format(self, mock_rm, mock_update, sample_seo_data):
        res = inject_video(
            wp_id=456,
            yt_id=\"TEST_VID_123\",
            seo=sample_seo_data,
            wp_base_url=\"https://vse.impresjapr.pl\",
            wp_user=\"admin\",
            wp_app_pass=\"pass\",
            skip_thumbnail=True,
            post_format=\"video\",
        )

        assert res[\"ok\"] is True
        mock_update.assert_called_once()
        _, kwargs = mock_update.call_args
        assert kwargs.get(\"post_format\") == \"video\"


# ---------------------------------------------------------------------------
# TASK-03: Responsive iframe embed inline styles
# ---------------------------------------------------------------------------

class TestTask03ResponsiveEmbed:

    def test_build_post_content_embed_inline_styles(self, sample_seo_data):
        content = build_post_content(
            seo=sample_seo_data,
            yt_id=\"TEST_VID_123\",
            upload_date=\"2026-10-24T12:00:00+02:00\",
        )

        assert 'style=\"aspect-ratio:16/9;width:100%;max-width:100%;position:relative;overflow:hidden;\"' in content
        assert \"padding-bottom:56.25%\" in content
        assert \"https://www.youtube.com/embed/TEST_VID_123?enablejsapi=1\" in content

    def test_build_wp_article_sections_embed_inline_styles(self, sample_seo_data):
        sections = build_wp_article_sections(
            seo=sample_seo_data,
            yt_id=\"TEST_VID_123\",
            include_embed=True,
        )

        html = sections[\"full_article_html\"]
        assert 'style=\"aspect-ratio:16/9;width:100%;max-width:100%;position:relative;overflow:hidden;\"' in html
        assert \"padding-bottom:56.25%\" in html
        assert \"<iframe\" in html


# ---------------------------------------------------------------------------
# TASK-04: Watch Page Schemas (SeekToAction, @id, Article, BreadcrumbList)
# ---------------------------------------------------------------------------

class TestTask04WatchPageSchemas:

    def test_video_object_has_id_and_seek_to_action(self, sample_seo_data):
        schemas = build_schema_jsonld(
            seo=sample_seo_data,
            yt_id=\"TEST_VID_123\",
            upload_date=\"2026-10-24T12:00:00+02:00\",
        )

        video_schema = next(s for s in schemas if s.get(\"@type\") == \"VideoObject\")
        assert video_schema[\"@id\"] == \"https://vse.impresjapr.pl/artykul-video-seo/#video\"

        actions = video_schema.get(\"potentialAction\")
        assert isinstance(actions, list)
        types = [a[\"@type\"] for a in actions]
        assert \"WatchAction\" in types
        assert \"SeekToAction\" in types

        seek = next(a for a in actions if a[\"@type\"] == \"SeekToAction\")
        assert \"{seek_to_second_number}\" in seek[\"target\"]
        assert \"seek_to_second_number\" in seek[\"startOffset-input\"]

    def test_article_and_breadcrumb_schemas_present(self, sample_seo_data):
        schemas = build_schema_jsonld(
            seo=sample_seo_data,
            yt_id=\"TEST_VID_123\",
            upload_date=\"2026-10-24T12:00:00+02:00\",
        )

        # Article schema
        article = next(s for s in schemas if s.get(\"@type\") == \"Article\")
        assert article[\"@id\"] == \"https://vse.impresjapr.pl/artykul-video-seo/#article\"
        assert article[\"mainEntityOfPage\"] == \"https://vse.impresjapr.pl/artykul-video-seo/\"
        assert article[\"video\"][\"@id\"] == \"https://vse.impresjapr.pl/artykul-video-seo/#video\"

        # BreadcrumbList schema
        breadcrumb = next(s for s in schemas if s.get(\"@type\") == \"BreadcrumbList\")
        items = breadcrumb[\"itemListElement\"]
        assert len(items) == 2
        assert items[0][\"position\"] == 1
        assert items[0][\"name\"] == \"Strona główna\"
        assert items[1][\"position\"] == 2
        assert items[1][\"item\"] == \"https://vse.impresjapr.pl/artykul-video-seo/\"


# ---------------------------------------------------------------------------
# TASK-05: watching_page Prompt & HCU Content Structure
# ---------------------------------------------------------------------------

class TestTask05WatchingPagePrompt:

    def test_watching_page_override_instructs_h3_and_length(self):
        override = _get_publication_type_override(\"watching_page\")
        assert \"300-450\" in override or \"300\" in override
        assert \"<h3>\" in override
        assert \"Google Watch Page 2026\" in override

    def test_pass1_watching_page_schema_retains_article_body(self):
        prompt_captured = []

        def mock_call(prompt, api_key, provider=\"gemini\"):
            prompt_captured.append(prompt)
            return json.dumps({
                \"focus_keyphrases\": [\"test\"],
                \"post_title\": \"Test Title\",
                \"seo_title\": \"Test SEO\",
                \"yt_title\": \"Test YT\",
                \"meta_description\": \"Desc\",
                \"lead\": \"Lead\",
                \"quotes\": [],
                \"chapters\": [],
                \"faq\": [],
                \"youtube_description_hook\": \"Hook\",
                \"youtube_hashtags\": [\"#a\"],
                \"video_description\": \"Desc\",
                \"tags\": [\"tag\"],
                \"external_links\": [],
                \"image_descriptions\": [],
                \"article_body\": \"<p>Wprowadzenie.</p><h3>Wątek 1</h3><p>Rozwinięcie tematu wideo.</p>\",
            })

        with patch(\"core.generator._call_llm\", side_effect=mock_call):
            generate_seo_v4(
                title=\"Wideo testowe\",
                timestamped_text=\"[00:00] Transkrypt testowy.\",
                total_duration=180.0,
                yt_url=\"https://www.youtube.com/watch?v=TEST_VID_123\",
                api_key=\"KEY\",
                publication_type=\"watching_page\",
            )

        assert len(prompt_captured) == 1
        assert '\"article_body\":\"<p>...</p><p>...</p>\"' in prompt_captured[0]


# ---------------------------------------------------------------------------
# TASK-06: Internal links deterministic fallback
# ---------------------------------------------------------------------------

class TestTask06InternalLinksFallback:

    def test_internal_links_block_rendered_when_not_in_body(self):
        seo = {
            \"article_body\": \"<p>Akapit bez żadnych linków zewnętrznych i wewnętrznych.</p>\",
            \"internal_links\": [
                {\"url\": \"https://vse.impresjapr.pl/artykul-1\", \"title\": \"Artykuł o SEO\"},
                {\"url\": \"https://vse.impresjapr.pl/artykul-2\", \"title\": \"Poradnik wideo\"},
            ],
        }

        block = _build_internal_links_block(seo)
        assert \"vse-related-links-box\" in block
        assert \"https://vse.impresjapr.pl/artykul-1\" in block
        assert \"Artykuł o SEO\" in block
        assert \"https://vse.impresjapr.pl/artykul-2\" in block

    def test_internal_links_block_skipped_when_already_woven(self):
        seo = {
            \"article_body\": \"<p>Jak pisaliśmy w artykule <a href='https://vse.impresjapr.pl/artykul-1'>SEO</a>, wideo jest ważne.</p>\",
            \"internal_links\": [
                {\"url\": \"https://vse.impresjapr.pl/artykul-1\", \"title\": \"Artykuł o SEO\"},
            ],
        }

        block = _build_internal_links_block(seo)
        assert block == \"\"

    def test_internal_links_block_empty_when_no_links(self):
        seo = {\"article_body\": \"<p>Tekst.</p>\", \"internal_links\": []}
        assert _build_internal_links_block(seo) == \"\"
