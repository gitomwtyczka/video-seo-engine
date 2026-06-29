"""Tests for D15 — _sanitize_llm_json() function in core/generator.py.

Test-Driven Development: tests written BEFORE implementation.

Covers:
  - Passthrough of valid JSON (no-op)
  - Malicious HTML attrs with double quotes inside JSON string values
  - Nested HTML tags with onclick containing double quotes
  - Escaped equations (e=\\"mc2\\") inside JSON strings
  - Multiline article_body with mixed HTML
  - Full dispatch test case from D15 spec
  - Preservation of HTML structure (no truncation of onclick handlers)

D15: DISPATCH-VSE-DEV-30-20260629-D15-SANITIZER-FIX
Agent: vse-dev-30 | 2026-06-29
"""
import json
import pytest

import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.generator import _sanitize_llm_json


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse(raw: str) -> dict:
    """Apply sanitizer and parse. Raises if still invalid."""
    sanitized = _sanitize_llm_json(raw)
    return json.loads(sanitized)


# ---------------------------------------------------------------------------
# Test: Passthrough on valid JSON (no-op)
# ---------------------------------------------------------------------------

class TestPassthrough:

    def test_valid_json_unchanged(self):
        """Valid JSON must be returned parseable — no corruption."""
        valid = json.dumps({
            "post_title": "Polityka polska 2026",
            "article_body": "<p>Tekst bez linkow.</p>",
            "tags": ["polityka", "polska"],
        })
        result = _parse(valid)
        assert result["post_title"] == "Polityka polska 2026"
        assert result["article_body"] == "<p>Tekst bez linkow.</p>"

    def test_valid_json_with_apostrophe_attrs(self):
        """Valid JSON with apostrophe-style HTML attrs — must parse cleanly."""
        valid = json.dumps({
            "article_body": "<a href='https://example.com' target='_blank'>link</a>",
        })
        result = _parse(valid)
        assert "href='https://example.com'" in result["article_body"]

    def test_valid_json_with_escaped_quotes(self):
        """Valid JSON with properly escaped quotes — must remain valid."""
        valid = json.dumps({
            "article_body": 'Cytat: \"mc squared\" jest wzorem'
        })
        result = _parse(valid)
        assert '"mc squared"' in result["article_body"]


# ---------------------------------------------------------------------------
# Test: HTML attributes with bare double quotes inside JSON string
# ---------------------------------------------------------------------------

class TestHtmlAttrWithDoubleQuotes:

    def test_href_double_quote_fixed(self):
        """Double-quoted href inside JSON string — must become parseable."""
        # This is what LLM produces that breaks json.loads():
        # {"article_body": "<a href=\"https://prawy.pl\" target=\"_blank\">link</a>"}
        # Raw bytes — simulate LLM output with unescaped quotes
        raw = '{"article_body": "<a href=\"https://prawy.pl\" target=\"_blank\">link</a>"}'
        result = _parse(raw)
        assert "https://prawy.pl" in result["article_body"]
        assert "link" in result["article_body"]

    def test_multiple_html_attrs_fixed(self):
        """Multiple double-quoted HTML attributes — all must be fixed."""
        raw = '{"article_body": "Tekst <a href=\"https://example.com\" target=\"_blank\" rel=\"nofollow\">anchor</a> koniec."}'
        result = _parse(raw)
        assert "https://example.com" in result["article_body"]
        assert "anchor" in result["article_body"]
        assert "koniec" in result["article_body"]

    def test_inline_equation_in_string(self):
        """e=\"mc2\" equation embedded in plain text — must not break JSON."""
        raw = '{"article_body": "To tekst i rownanie e=\\\"mc2\\\", a to dalszy tekst."}'
        result = _parse(raw)
        assert "mc2" in result["article_body"]


# ---------------------------------------------------------------------------
# Test: onclick and nested HTML attrs
# ---------------------------------------------------------------------------

class TestOnclickPreservation:

    def test_onclick_not_truncated(self):
        """onclick handler with double quotes — must NOT be truncated.

        This is the key failure mode of the naive regex:
        onclick=\"alert('TEST')\" — naive regex might cut after 'alert'.
        """
        # Full D15 dispatch test case
        raw = json.dumps({
            "article_body": 'To tekst i rownanie e=\\"mc2\\", a to link <a href=\\"#\\">klik</a>. Script: onclick=\\"alert(\'TEST\')\"'
        })
        # Now simulate unescaped double quotes in HTML attrs (LLM bug)
        raw_llm = '{"article_body": "To tekst i rownanie e=\\"mc2\\", a to link <a href=\"#\">klik</a>. Script: onclick=\"alert(\'TEST\')\""}'
        result = _parse(raw_llm)
        body = result["article_body"]
        # href must be present
        assert "href" in body or "#" in body, f"href missing in: {body!r}"
        # onclick must be preserved (not truncated)
        assert "alert" in body, f"onclick alert truncated in: {body!r}"
        assert "TEST" in body, f"onclick TEST truncated in: {body!r}"

    def test_multiple_html_elements_preserved(self):
        """Multiple HTML elements with double-quoted attrs — all intact."""
        raw_llm = ('{"article_body": "Para <strong>bold</strong>. '
                   '<a href=\"https://wikipedia.org\" target=\"_blank\">Wiki</a>. '
                   '<img src=\"photo.jpg\" alt=\"Opis\">.</p>"}')
        result = _parse(raw_llm)
        body = result["article_body"]
        assert "strong" in body
        assert "wikipedia.org" in body
        assert "photo.jpg" in body


# ---------------------------------------------------------------------------
# Test: Full D15 dispatch spec test case
# ---------------------------------------------------------------------------

class TestDispatchSpecTestCase:

    def test_full_d15_spec_case(self):
        """Exact test case from D15 dispatch specification.

        Input (LLM-broken): article_body with e=\"mc2\", href=\"#\", onclick=\"...\"
        Expected: JSON parseable, HTML structure intact, onclick not truncated.
        """
        # This is the raw string LLM would produce (breaking json.loads):
        raw_llm = (
            '{"article_body": "To tekst i rownanie e=\\"mc2\\", '
            'a to link <a href=\"#\">klik</a>. '
            'Script: onclick=\\"alert(\'TEST\')\"."}'
        )
        result = _parse(raw_llm)
        body = result["article_body"]
        assert "mc2" in body, f"mc2 missing: {body!r}"
        assert "klik" in body, f"klik link missing: {body!r}"
        assert "alert" in body, f"onclick alert missing: {body!r}"
        assert "TEST" in body, f"onclick TEST missing: {body!r}"

    def test_full_seo_json_with_broken_html(self):
        """Full SEO JSON with broken HTML in article_body — all other fields preserved."""
        # Simulate complete LLM output with broken HTML in article_body only
        raw_llm = (
            '{"post_title": "Polityka obronna Polski", '
            '"wp_slug": "polityka-obronna-polski", '
            '"article_body": "<p>Artykul o <a href=\"https://mon.gov.pl\" target=\"_blank\">MON</a>.</p>", '
            '"tags": ["polityka", "obronnosc"]}'
        )
        result = _parse(raw_llm)
        assert result["post_title"] == "Polityka obronna Polski"
        assert result["wp_slug"] == "polityka-obronna-polski"
        assert result["tags"] == ["polityka", "obronnosc"]
        assert "mon.gov.pl" in result["article_body"]
        assert "MON" in result["article_body"]


# ---------------------------------------------------------------------------
# Test: Multiline and complex bodies
# ---------------------------------------------------------------------------

class TestMultilineBody:

    def test_multiline_article_body(self):
        """Multiline article_body (with \\n) — must survive sanitization."""
        raw_llm = (
            '{"article_body": "Akapit 1.\\n'
            '<p>Akapit 2 z <a href=\"https://pap.pl\" target=\"_blank\">PAP</a>.</p>\\n'
            '<p>Akapit 3.</p>"}'
        )
        result = _parse(raw_llm)
        assert "PAP" in result["article_body"]
        assert "pap.pl" in result["article_body"]
        assert "Akapit 3" in result["article_body"]

    def test_sanitizer_does_not_corrupt_plain_text(self):
        """Plain text without HTML — sanitizer must not corrupt it."""
        valid = json.dumps({
            "post_title": "Tytuł artykułu",
            "meta_description": "Opis zawierający specjalne znaki: & < > i polskie: ąćę.",
        })
        result = _parse(valid)
        assert "&" in result["meta_description"]
        assert "ąćę" in result["meta_description"]

    def test_sanitizer_returns_string(self):
        """_sanitize_llm_json must return a string (not dict)."""
        raw = json.dumps({"x": "y"})
        out = _sanitize_llm_json(raw)
        assert isinstance(out, str), f"Expected str, got {type(out)}"
