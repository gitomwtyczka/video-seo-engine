"""AI Schema Generator — VideoObject, Clip (chapters), FAQPage via Gemini API.

Migrated from: test_full_seo_v4.py (shadow-perihelion / D:\\Biblioteki\\prawy.pl)
Migration by: vse-architect-01 | DISPATCH-VSE-ARCHITECT-02 | 2026-05-13

Responsibilities:
  - Parse VTT transcript into timestamped segments
  - Call LLM (Gemini or Claude) to generate SEO-optimized titles, descriptions, chapters, FAQ
  - Anchor-match LLM chapter labels to exact VTT timestamps (fuzzy)
  - Return schema-ready dict for injector.py

Schema standards (Google 2026):
  - duration: ISO 8601 (PT#H#M#S)
  - uploadDate: ISO 8601 with timezone (e.g. 2026-01-15T10:00:00+01:00)
  - interactionStatistic: WatchAction + userInteractionCount (from YouTube)
  - SeekToAction: added for completeness (not rendered for PL content)
  - Quotation: NOT added (Google does not render; keep if existing)
  - Default model: gemini-2.5-flash | Claude: claude-3-5-sonnet-20241022

SAAS Enrichment (2026-06-17, vse-dev-14):
  - generate_seo_v4() accepts optional priority_keywords and internal_links

Branding fix (2026-06-19, vse-dev-17):
  - generate_seo_v4() accepts optional site_brand parameter

D5 Multi-keyword (2026-06-20, vse-dev-19):
  - LLM prompt now requests focus_keyphrases (list of 2-3 phrases)

D6b Publication types (2026-06-20, vse-dev-21):
  - generate_seo_v4() and process_video() accept publication_type parameter
  - Three types: full_analysis (default), watching_page, discover
  - Each type modifies the LLM prompt for article_body length/format

D1 Two-Pass Content Pipeline:
  - Pass 1: Schema generation (no article_body)
  - Pass 2: Article generation via PressAI M2M or local fallback LLM

D10 Smart External Links (2026-06-21, vse-dev-25):
  - LLM prompt requests external_links (2-3 authority DoFollow links)
  - article_body MUST contain woven <a> tags to authority sources
  - Sources: Wikipedia PL, .gov.pl, PAP, Reuters, AP, think-tanks

D11 Image Descriptions Fallback (2026-06-21, vse-dev-26):
  - LLM prompt requests image_descriptions (2 descriptions for video screenshots)
  - Used ONLY as fallback when SAAS Vision API is unavailable
  - SAAS primary (GPT-4o Vision sees actual image) vs LLM blind descriptions

D12 JSON Resilience (2026-06-21, vse-dev-27):
  - Log raw LLM output on json.loads() failure for debugging
  - 1 retry with fix prompt on JSONDecodeError
  - Prompt fix: instruct HTML attributes to use apostrophes (') not quotes (")
  - Root cause: Claude doesn't escape " in HTML attrs inside JSON strings

D13 Slug Trim (2026-06-21, vse-dev-29):
  - Hard limit 60 chars on wp_slug (trim to last full word)
  - Prompt updated: preserve Polish conjunctions (i, w, z, na, do, o) in slug
    when they are part of the focus keyphrase — fixes RankMath false positive
  - Bugfix: resolved_channels → resolved_chapters (typo from original code)

D15 JSON Sanitizer (2026-06-29, vse-dev-30):
  - _sanitize_llm_json() applied before json.loads() in generate_seo_v4()
  - PRIMARY: json-repair library (pip install json-repair) — structural repair
  - FALLBACK: regex restricted to HTML attr values (attr=\\\"val\\\" → attr='val')
  - Zero false positives on plain text, multiline, nested HTML
  - Eliminates 500 errors from LLM outputting raw HTML with unescaped quotes

KROK B (2026-10-20, vse-dev-01):
  - Twarda blokada anty-konfabulacyjna: całkowity zakaz generowania pakietu SEO
    lub artykułu z samego tytułu bez transkryptu (>= 50 znaków).
  - Korekta stylistyczna i interpunkcyjna transkryptu: pole `clean_transcript`
    w wynikowym słowniku `result` (zredagowany zapis z timestampami `[MM:SS]` co akapit,
    oczyszczony z wypełniaczy ASR typu 'yyy', 'eee') oraz jawna instrukcja ASR
    w promptach Pass 1 i Pass 2 dot. korygowania błędów fonetycznych nazwisk i nazw własnych.

VTT Limit fix (2026-07-14, Supervisor-01):
  - text_trimmed limit raised from 80000 → 200000 chars
  - Covers ~90 min of conversation (avg 2200 char/min post-parse)
  - Safe for Gemini 2.5 Flash (1M token ctx) and Claude Sonnet (200k token ctx)

Dependencies:
  pip install google-genai anthropic python-dotenv json-repair
"""
import contextvars
import json
import logging
import os
import re
import time
from difflib import SequenceMatcher
from typing import Optional

logger = logging.getLogger(__name__)

# Kontekstowy licznik tokenów LLM (thread/async-safe per wywołanie process_video)
current_llm_usage: contextvars.ContextVar[Optional[dict]] = contextvars.ContextVar("current_llm_usage", default=None)

ASR_PHONETIC_INSTRUCTION = (
    "Transkrypt pochodzi z automatycznego rozpoznawania mowy (ASR) i może zawierać "
    "fonetyczne przekręcenia nazwisk, nazw własnych lub potoczne wtrącenia ('yyy', powtórzenia). "
    "Zawsze koryguj oczywiste błędy fonetyczne ASR zgodnie z kontekstem wypowiedzi i tytułem materiału "
    "(np. nazwiska autorów i gości z tytułu filmu)."
)


def calculate_cost_usd(provider: str, input_tokens: int, output_tokens: int) -> float:
    """Oblicza szacunkowy koszt w USD na podstawie tokenów wejściowych i wyjściowych."""
    if provider == "gemini":
        return round((input_tokens * 0.075 + output_tokens * 0.30) / 1_000_000, 6)
    elif provider == "claude":
        return round((input_tokens * 3.00 + output_tokens * 15.00) / 1_000_000, 6)
    return 0.0

# D15: json-repair optional import (PRIMARY sanitizer backend)
try:
    from json_repair import repair_json as _json_repair_fn  # type: ignore
    _JSON_REPAIR_AVAILABLE = True
except ImportError:
    _JSON_REPAIR_AVAILABLE = False
    logger.warning("D15: json-repair not installed — using regex fallback. pip install json-repair")


# ============================================================
# MULTI-LANGUAGE & CROSS-LANGUAGE CONFIGURATION
# ============================================================

SUPPORTED_LANGUAGES: dict[str, dict[str, str]] = {
    "pl": {"name": "polski (Polish)", "eeat_sources": "pl.wikipedia.org, gov.pl, stat.gov.pl, pap.pl, nbp.pl", "WatchAction": "Obejrzyj wideo", "summary_heading": "Podsumowanie"},
    "en": {"name": "angielski (English)", "eeat_sources": "en.wikipedia.org, reuters.com, apnews.com, .gov, .edu, who.int", "WatchAction": "Watch video", "summary_heading": "Summary"},
    "de": {"name": "niemiecki (German)", "eeat_sources": "de.wikipedia.org, bund.de, destatis.de, tagesschau.de", "WatchAction": "Video ansehen", "summary_heading": "Zusammenfassung"},
    "es": {"name": "hiszpański (Spanish)", "eeat_sources": "es.wikipedia.org, ine.es, efe.com, boe.es", "WatchAction": "Ver video", "summary_heading": "Resumen"},
    "fr": {"name": "francuski (French)", "eeat_sources": "fr.wikipedia.org, insee.fr, service-public.fr, afp.com", "WatchAction": "Regarder la vidéo", "summary_heading": "Résumé"},
    "it": {"name": "włoski (Italian)", "eeat_sources": "it.wikipedia.org, istat.it, gov.it, ansa.it", "WatchAction": "Guarda il video", "summary_heading": "Riassunto"},
    "uk": {"name": "ukraiński (Ukrainian)", "eeat_sources": "uk.wikipedia.org, gov.ua, ukrstat.gov.ua, ukrinform.ua", "WatchAction": "Дивитися відео", "summary_heading": "Підсумок"},
    "pt": {"name": "portugalski (Portuguese)", "eeat_sources": "pt.wikipedia.org, gov.br, ibge.gov.br, ine.pt, lusa.pt", "WatchAction": "Assistir vídeo", "summary_heading": "Resumo"},
}


# ============================================================
# FORMAT INSTRUCTIONS (Pass 2)
# ============================================================

FORMAT_INSTRUCTIONS: dict[str, str] = {
    "analiza": "Napisz pogłębioną analizę: teza → dane/dowody → analiza wieloaspektowa → wnioski → prognozy. Minimum 3 Śródtła/przykłady. Styl: merytoryczny, bez kolokwializmow.",
    "news": "Napisz newsa: odwrócona piramida, 5W+H w leadzie, 1 akapit tła, co dalej. Styl: zwarty, rzeczowy.",
    "explainer": "Wyjaśnij mechanizm: co to jest, dlaczego ważne, jak działa, co to oznacza dla czytelnika. Prosty język.",
    "wywiad": "Napisz wywiad Q&A: krótki wstęp redakcyjny (2-3 zdania) + dialog pytanie-odpowiedź z transkryptu.",
    "poradnik": "Napisz poradnik: problem → kroki rozwiązania (numerowane) → wskazówki praktyczne.",
    "felieton": "Napisz felieton: styl autorski, ironia, metafory. Mocna puenta na końcu.",
    "reportaz": "Napisz reportaż: immersyjna narracja, sceny, konkrety, detale.",
    # Backward compat
    "full_analysis": "Napisz pogłębiony artykuł analityczny.",
    "watching_page": "Napisz krótki opis wideo (2-3 akapity). Styl: informacyjny.",
    "discover": "Krótki artykuł Discover (500-600 słów). Zasady Google Discover 2026: TYTUŁ: Sedno informacji w tytule — zakaz clickbaitu i curiosity gap. Czytelnik musi wiedzieć co dostanie. LEAD: Rzetelny, informacyjny — odpowiada na 'co i dlaczego ważne', nie 'jak bardzo zaskakujące'. STRUKTURA: max 2 śródtytuły H3, krótkie akapity (2-3 zdania), prosty język. ZAKAZ: Tytułów zaczynających się od pytania retorycznego ('Czy wiesz że...', 'Oto dlaczego...'). Fraza kluczowa naturalna, wpleciona bez wymuszania.",
}

def _get_target_words(publication_type: str) -> int:
    return {
        "analiza": 1000, "reportaz": 1200, "wywiad": 900,
        "news": 600, "explainer": 800, "poradnik": 800,
        "felieton": 700, "full_analysis": 800,
        "watching_page": 400, "discover": 500,
    }.get(publication_type, 800)


# ============================================================
# DURATION UTILS
# ============================================================

def format_duration_iso(seconds: float) -> str:
    """Convert total seconds to ISO 8601 duration string (PT#H#M#S).

    Args:
        seconds: Total duration in seconds.

    Returns:
        ISO 8601 duration string, e.g. 'PT1H23M45S'.
    """
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    parts = "PT"
    if h:
        parts += f"{h}H"
    parts += f"{m}M{s}S"
    return parts


# ============================================================
# VTT PARSER & CLEAN TRANSCRIPT FORMATTER
# ============================================================

_ASR_FILLER_RE = re.compile(
    r"\b(?:y{2,}|e{2,}|mhm+|yyy+|eee+|hm+|uh+|um+)\b[,\s]*",
    flags=re.IGNORECASE,
)


def build_clean_transcript_from_segments(segments: list[tuple[float, str]], interval_sec: float = 45.0) -> str:
    """Buduje czytelny, podzielony na akapity transkrypt z zachowaniem timestampów [MM:SS] co akapit
    oraz oczyszczeniem z wypełniaczy ASR ('yyy', 'eee') i powtórzeń."""
    if not segments:
        return ""
    paragraphs: list[str] = []
    current_words: list[str] = []
    para_start_ts: Optional[float] = None

    for ts, raw_text in segments:
        cleaned = _ASR_FILLER_RE.sub("", raw_text).strip()
        cleaned = re.sub(r"\b(\w+)(?:\s+\1\b)+", r"\1", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
        if not cleaned:
            continue
        if para_start_ts is None:
            para_start_ts = ts
        current_words.append(cleaned)
        joined_len = sum(len(x) for x in current_words)
        if (ts - para_start_ts >= interval_sec and joined_len >= 180) or joined_len >= 420:
            minutes = int(para_start_ts // 60)
            seconds = int(para_start_ts % 60)
            body = " ".join(current_words).strip()
            if body and body[0].islower():
                body = body[0].upper() + body[1:]
            if body and body[-1] not in ".!?…":
                body += "."
            paragraphs.append(f"[{minutes:02d}:{seconds:02d}] {body}")
            current_words = []
            para_start_ts = None

    if current_words and para_start_ts is not None:
        minutes = int(para_start_ts // 60)
        seconds = int(para_start_ts % 60)
        body = " ".join(current_words).strip()
        if body and body[0].islower():
            body = body[0].upper() + body[1:]
        if body and body[-1] not in ".!?…":
            body += "."
        paragraphs.append(f"[{minutes:02d}:{seconds:02d}] {body}")

    return "\n\n".join(paragraphs)


def parse_vtt_full(vtt_path: str) -> tuple[str, list[tuple[float, str]], float]:
    """Parse a WebVTT file into timestamped text, segments list, and total duration."""
    with open(vtt_path, "r", encoding="utf-8") as f:
        content = f.read()

    segments: list[tuple[float, str]] = []
    current_time = 0.0
    max_time = 0.0

    for line in content.split("\n"):
        line = line.strip()
        ts_match = re.match(r"^(\d{2}):(\d{2}):(\d{2}[\.,]\d+)\s*-->", line)
        if ts_match:
            h, m, s = ts_match.groups()
            s = s.replace(",", ".")
            current_time = int(h) * 3600 + int(m) * 60 + float(s)
            if current_time > max_time:
                max_time = current_time
            continue
        if not line or line.startswith("WEBVTT") or line.startswith("Kind:") or line.startswith("Language:"):
            continue
        if re.match(r"^\d+$", line):
            continue
        clean = re.sub(r"<[^>]+>", "", line)
        clean = clean.replace("&gt;&gt;", "").strip()
        if clean and len(clean) > 3:
            segments.append((current_time, clean))

    # Deduplicate — keep first occurrence of each line
    seen: set[str] = set()
    unique: list[tuple[float, str]] = []
    for ts, text in segments:
        if text not in seen:
            seen.add(text)
            unique.append((ts, text))

    if not unique:
        raise ValueError(f"VTT file parsed to 0 usable segments: {vtt_path}")

    # Build marked text with 30s interval markers
    parts: list[str] = []
    last_marker = -30.0
    for ts, text in unique:
        if ts - last_marker >= 30:
            minutes = int(ts // 60)
            seconds = int(ts % 60)
            parts.append(f"\n[{minutes:02d}:{seconds:02d}] ")
            last_marker = ts
        parts.append(text + " ")

    return "".join(parts), unique, max_time


# ============================================================
# ANCHOR MATCHING — fuzzy VTT lookup
# ============================================================

def find_anchor_in_vtt(anchor_text: str, segments: list[tuple[float, str]]) -> int:
    """Find the VTT timestamp where anchor_text first appears."""
    anchor_clean = anchor_text.lower().strip()
    if not anchor_clean or not segments:
        return -1

    anchor_words = [w for w in re.findall(r"\w+", anchor_clean) if len(w) >= 4]
    best_score = 0.0
    best_time = -1

    for window_size in [3, 5, 2, 1]:
        for i in range(len(segments) - window_size + 1):
            window_text = " ".join(seg[1] for seg in segments[i : i + window_size]).lower()

            if anchor_clean in window_text:
                return int(segments[i][0])

            # Fast pre-filter: skip expensive SequenceMatcher if no significant word overlaps
            if anchor_words and not any(w in window_text for w in anchor_words):
                continue

            score = SequenceMatcher(None, anchor_clean, window_text[: len(anchor_clean) * 2]).ratio()
            if score > best_score:
                best_score = score
                best_time = int(segments[i][0])

        if best_score > 0.72:
            return best_time

    if best_score > 0.5:
        return best_time

    return -1


# ============================================================
# LLM ABSTRACTION — Gemini + Claude
# ============================================================

def _call_llm(prompt: str, api_key: str, provider: str = "gemini") -> str:
    """Call LLM provider with prompt, return raw text response."""
    if provider == "claude":
        try:
            import anthropic  # type: ignore
            client = anthropic.Anthropic(api_key=api_key)
            model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")
            msg = client.messages.create(
                model=model,
                max_tokens=8192,
                messages=[{"role": "user", "content": prompt}],
            )
            usage = getattr(msg, "usage", None)
            in_tok = getattr(usage, "input_tokens", 0) if usage else 0
            out_tok = getattr(usage, "output_tokens", 0) if usage else 0
            logger.info("LLM Claude (%s) usage: input=%d, output=%d tokens", model, in_tok, out_tok)
            tracker = current_llm_usage.get()
            if tracker is not None:
                tracker["input_tokens"] += in_tok
                tracker["output_tokens"] += out_tok
                tracker["last_provider"] = "claude"
            return msg.content[0].text
        except Exception as e:
            logger.warning(
                "Claude LLM failed (%s: %s). Activating automatic fallback to gemini-2.5-flash.",
                type(e).__name__,
                e,
            )
            provider = "gemini"
            api_key = os.getenv("GEMINI_API_KEY", api_key)

    if provider == "gemini":
        from google import genai  # type: ignore
        client = genai.Client(api_key=api_key)
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        usage = getattr(resp, "usage_metadata", None)
        in_tok = getattr(usage, "prompt_token_count", 0) if usage else 0
        out_tok = getattr(usage, "candidates_token_count", 0) if usage else 0
        logger.info("LLM Gemini (gemini-2.5-flash) usage: input=%d, output=%d tokens", in_tok, out_tok)
        tracker = current_llm_usage.get()
        if tracker is not None:
            tracker["input_tokens"] += in_tok
            tracker["output_tokens"] += out_tok
            tracker["last_provider"] = "gemini"
        return resp.text
    else:
        raise ValueError(f"Unsupported LLM provider: {provider!r}. Use 'gemini' or 'claude'.")


# ============================================================
# PASS 2 ARTICLE GENERATION
# ============================================================

def _generate_article_fallback(
    schema: dict,
    vtt_text: str,
    publication_type: str,
    api_key: str,
    provider: str = "gemini",
    target_words: int = 800,
    target_lang: str = "pl",
    source_lang: str = "auto",
) -> str:
    """Fallback: generuj długi artykuł lokalnym LLM gdy PressAI niedostępny."""
    keyphrase = schema.get("focus_keyphrases", [""])[0] if schema.get("focus_keyphrases") else ""
    instruction = FORMAT_INSTRUCTIONS.get(publication_type, FORMAT_INSTRUCTIONS["full_analysis"])
    post_title = schema.get("post_title", "")
    original_title = schema.get("original_title", post_title)
    lang_cfg = SUPPORTED_LANGUAGES.get(target_lang, SUPPORTED_LANGUAGES["pl"])
    lang_name = lang_cfg["name"]
    summary_heading = lang_cfg.get("summary_heading", "Podsumowanie")
    eeat_sources = lang_cfg["eeat_sources"]

    prompt = f"""Jesteś doświadczonym redaktorem portalu. Napisz kompletny artykuł na podstawie transkryptu wideo.

KRYTYCZNA DYREKTYWA JĘZYKOWA (CROSS-LANGUAGE):
- Język źródłowy transkryptu: {source_lang}
- JĘZYK DOCELOWY ARTYKUŁU: **{lang_name} ({target_lang.upper()})**
- Cały artykuł HTML (lead, akapity <p>, śródtytuły <h2> i <h3>, cytaty <blockquote> oraz sekcja podsumowania '<h2>{summary_heading}</h2>') MUSI być napisany w 100% w języku **{lang_name}**!
- Używaj naturalnej gramatyki, stylistyki i idiomów języka {lang_name}. Jeśli wplatasz linki E-E-A-T, preferuj źródła dla tego języka: {eeat_sources}.

KOREKTA BŁĘDÓW ASR:
- {ASR_PHONETIC_INSTRUCTION}
- Oryginalny tytuł filmu: {original_title}

FRAZA KLUCZOWA: {keyphrase}
TYTUŁ: {post_title}
FORMAT: {instruction}
CEL DŁUGOŚCI: minimum {target_words} słów

ZASADY HTML:
- Używaj <h2>, <h3>, <p>, <blockquote> (NIE <html>, <head>, <body>)
- Apostrofy (') w atrybutach HTML, NIE cudzysłowy
- Co 150-200 słów nowy nagłówek <h3> (w języku {lang_name})
- Na końcu sekcja podsumowania z nagłówkiem <h2>{summary_heading}</h2>
- Fraza kluczowa naturalnie minimum 3x w tekście
- Pierwszy akapit zawiera główną frazę
- Znacznik przed FAQ: <hr id='system-readmore' />

TRANSKRYPT:
{vtt_text[:120000]}

Zwróć TYLKO HTML artykułu w języku {lang_name} (bez JSON, bez wyjaśnień):"""
    
    logger.info(
        "_generate_article_fallback: type=%s target=%d words provider=%s target_lang=%s source_lang=%s",
        publication_type, target_words, provider, target_lang, source_lang,
    )
    return _call_llm(prompt, api_key, provider)


async def generate_article_content(
    schema: dict,
    vtt_text: str,
    publication_type: str,
    api_key: str,
    provider: str = "gemini",
    pressai_api_url: str = "",
    pressai_token: str = "",
    internal_links: Optional[list[dict]] = None,
    target_lang: str = "pl",
    source_lang: str = "auto",
) -> tuple[str, str]:
    """Pass 2: generuje długi artykuł (600-1200+ słów) w języku `target_lang`."""
    FORMAT_MAP = {
        "analiza": "analiza", "news": "news", "explainer": "explainer",
        "wywiad": "wywiad", "poradnik": "poradnik", "felieton": "felieton",
        "reportaz": "reportaz",
        "full_analysis": "analiza", "watching_page": "news", "discover": "news",
    }
    target_words = _get_target_words(publication_type)
    pressai_format = FORMAT_MAP.get(publication_type, "analiza")
    
    # Próba PressAI M2M (tylko dla języka polskiego lub gdy obsługuje target_lang)
    if pressai_api_url and pressai_token and target_lang == "pl":
        try:
            import httpx
            payload = {
                "focus_keyphrase": schema.get("focus_keyphrases", [""])[0] if schema.get("focus_keyphrases") else "",
                "keyphrases": schema.get("focus_keyphrases", []),
                "transcript": vtt_text[:200000],
                "title": schema.get("post_title", ""),
                "format": pressai_format,
                "target_words": target_words,
                "internal_links": internal_links or [],
                "source": "vse",
                "lang": target_lang,
            }
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{pressai_api_url}/api/external/generate-article",
                    json=payload,
                    headers={"Authorization": f"Bearer {pressai_token}"},
                )
                resp.raise_for_status()
                data = resp.json()
                article_html = data.get("article_body", "")
                if article_html and len(article_html) > 200:
                    logger.info("Pass 2: PressAI article (%d chars)", len(article_html))
                    return article_html, "pressai"
                logger.warning("Pass 2: PressAI returned short/empty article, using fallback")
        except Exception as e:
            logger.warning("Pass 2: PressAI failed (%s) — falling back to local LLM", e)
    
    # Fallback: lokalny LLM (wspiera wszystkie 8 języków target_lang)
    article_html = _generate_article_fallback(
        schema=schema, vtt_text=vtt_text,
        publication_type=publication_type,
        api_key=api_key, provider=provider,
        target_words=target_words,
        target_lang=target_lang,
        source_lang=source_lang,
    )
    return article_html, "local_fallback"


# ============================================================
# D15: JSON SANITIZER — pre-parse repair for LLM HTML output
# ============================================================

def _sanitize_llm_json(raw_text: str) -> str:
    """Sanitize raw LLM output before json.loads() to prevent JSONDecodeError."""
    # Fast path: already valid JSON — no work needed
    try:
        json.loads(raw_text)
        return raw_text
    except json.JSONDecodeError:
        pass

    # PRIMARY: json-repair — structural, safe, handles multiline and nesting
    if _JSON_REPAIR_AVAILABLE:
        try:
            repaired = _json_repair_fn(raw_text, return_objects=False)
            # json-repair may return a dict; ensure we have a string
            if isinstance(repaired, dict):
                repaired = json.dumps(repaired, ensure_ascii=False)
            # Validate repair worked
            json.loads(repaired)
            logger.info("D15: json-repair fixed LLM output (%d → %d chars)", len(raw_text), len(repaired))
            return repaired
        except Exception as repair_exc:
            logger.warning("D15: json-repair failed (%s) — trying regex fallback", repair_exc)

    # FALLBACK: regex — restricted to HTML attribute values only
    try:
        fixed = re.sub(
            r'(\b[\w-]+)=\\"((?:[^\\"]|\\.)*)\\"',
            r"\1='\2'",
            raw_text,
        )
        json.loads(fixed)
        logger.info("D15: regex fallback fixed LLM output")
        return fixed
    except (json.JSONDecodeError, re.error) as regex_exc:
        logger.warning(
            "D15: regex fallback also failed (%s) — returning raw for D12 retry",
            regex_exc,
        )

    # Both strategies failed — return raw text; D12 retry will handle or raise
    return raw_text


# ============================================================
# SAAS ENRICHMENT — build prompt section from GSC data
# ============================================================

def _build_saas_prompt_section(
    priority_keywords: Optional[list[str]] = None,
    internal_links: Optional[list[dict]] = None,
) -> str:
    """Build an additional prompt section with SAAS enrichment data."""
    sections = []

    if priority_keywords:
        kw_list = ", ".join(f'"{ kw}"' for kw in priority_keywords[:15])
        sections.append(f"""## PRIORYTETOWE FRAZY KLUCZOWE Z GSC PORTALU

Poniższe frazy są faktycznie wyszukiwane przez użytkowników Google i portal już na nie rankuje.
Użyj ich naturalnie w article_body, meta_description, lead i FAQ — ale TYLKO jeśli pasują
tematycznie do tego materiału wideo. Nie forsuj fraz na siłę.

Frazy: {kw_list}""")

    if internal_links:
        links_text = "\n".join(
            f"- {link['url']} ({link.get('title', '')})" for link in internal_links[:10]
        )
        sections.append(f"""## PROPOZYCJE LINKOW WEWNETRZNYCH

Poniższe strony to najpopularniejsze artykuły portalu. Jeśli którykolwiek jest tematycznie
powiązany z omawianym materiałem wideo, wstaw link w article_body jako naturalny anchor
(np. "jak pisaliśmy w [temat](url)"). Max 2-3 linki, tylko jeśli pasują.

{links_text}""")

    if not sections:
        return ""

    return "\n\n" + "\n\n".join(sections) + "\n"


# ============================================================
# D6b.6: PUBLICATION TYPE PROMPT OVERRIDES
# ============================================================

def _get_publication_type_override(publication_type: str) -> str:
    """Get prompt override section for a specific publication type."""
    if publication_type == "watching_page":
        return """

## UWAGA — TYP PUBLIKACJI: WATCHING PAGE

To jest krótki artykuł typu "strona oglądania" z embedem wideo.
Zastosuj ZMODYFIKOWANE reguły:
- **article_body**: MAX 2 krótkie akapity <p> (300-500 zn). Skup się na
  krótkim opisie o czym jest materiał i dlaczego warto obejrzeć.
  NIE pisz rozbudowanej analizy.
- **chapters**: generuj normalnie (pełna lista)
- **faq**: MAX 2 pytania (krótkie, najważniejsze)
- **quotes**: MAX 2 cytaty
- Reszta pól (tytuły, meta, lead) — bez zmian
"""
    elif publication_type == "discover":
        return """

## UWAGA — TYP PUBLIKACJI: GOOGLE DISCOVER

To jest krótki artykuł Discover (500-600 słów). Zasady Google Discover 2026:
- **post_title**: max 65 zn. Sedno informacji w tytule — zakaz clickbaitu i curiosity gap. Czytelnik musi wiedzieć co dostanie. ZAKAZ tytułów zaczynających się od pytania retorycznego ('Czy wiesz że...', 'Oto dlaczego...').
- **lead**: 1-2 zdania, max 150 zn. Rzetelny, informacyjny — odpowiada na 'co i dlaczego ważne', nie 'jak bardzo zaskakujące'.
- **article_body**: max 2 śródtytuły H3, krótkie akapity (2-3 zdania), prosty język. Formatuj pod mobile: krótkie zdania, dużo enterów. Fraza kluczowa naturalna, wpleciona bez wymuszania.
- **faq**: POMIŃ (nie generuj FAQ dla Discover)
- **quotes**: MAX 2 krótkie cytaty
- **chapters**: generuj normalnie
"""
    else:  # full_analysis or unknown — no override
        return ""


# ============================================================
# SEO GENERATION — prompt v5.8 + slug hard limit D13 + KROK B ASR
# ============================================================

def generate_seo_v4(
    title: str,
    timestamped_text: str,
    total_duration: float,
    yt_url: str,
    api_key: str,
    provider: str = "gemini",
    priority_keywords: Optional[list[str]] = None,
    internal_links: Optional[list[dict]] = None,
    site_brand: Optional[str] = None,
    publication_type: str = "full_analysis",
    target_lang: str = "pl",
    source_lang: str = "auto",
) -> dict:
    """Call LLM to generate full SEO package for a video."""
    text_trimmed = timestamped_text[:200000]  # ~90 min @ avg 2200 char/min post-parse (raised from 80k, Supervisor-01 2026-07-14)
    total_min = int(total_duration // 60)

    if total_min <= 15:
        faq_range, ch_range, qt_range = "2-3", "5-7", "2-3"
    elif total_min <= 30:
        faq_range, ch_range, qt_range = "3-5", "6-10", "3-5"
    elif total_min <= 45:
        faq_range, ch_range, qt_range = "4-6", "8-12", "4-6"
    else:
        faq_range, ch_range, qt_range = "5-8", "10-15", "5-7"

    total_sec = int(total_duration % 60)

    # Build SAAS enrichment section (empty string if no data)
    saas_section = _build_saas_prompt_section(priority_keywords, internal_links)

    # Build seo_title instruction based on site_brand availability
    if site_brand:
        seo_title_instruction = (
            f"**seo_title** \u2014 max 60 znakow, dla tagu <title> i RankMath. "
            f'Z branding pipe: "| {site_brand}". Moze byc krotsza wersja post_title.'
        )
    else:
        seo_title_instruction = (
            "**seo_title** \u2014 max 60 znakow, dla tagu <title> i RankMath. "
            "Moze byc krotsza wersja post_title. Bez branding pipe."
        )

    # D6b.6: Publication type override
    pub_type_section = _get_publication_type_override(publication_type)

    target_lang = (target_lang or "pl").lower()[:2]
    if target_lang not in SUPPORTED_LANGUAGES:
        target_lang = "pl"
    lang_cfg = SUPPORTED_LANGUAGES[target_lang]
    target_lang_name = lang_cfg["name"]
    eeat_sources = lang_cfg["eeat_sources"]

    portal_desc = f"redaktorem portalu {site_brand}" if site_brand else "doświadczonym redaktorem portalu informacyjnego"
    prompt = f"""Jestes ekspertem SEO i {portal_desc}.

## DYREKTYWA JĘZYKOWA (CROSS-LANGUAGE ENGINE — DUAL-LANGUAGE ANCHOR)
- Język oryginalnego transkryptu wideo (SOURCE_LANG): {source_lang}
- Język docelowy wszystkich wygenerowanych materiałów SEO (TARGET_LANG): {target_lang_name} (kod ISO: {target_lang})
- WSZYSTKIE pola widoczne dla czytelnika (focus_keyphrases, post_title, seo_title, yt_title, meta_description, lead, chapters[].label, quotes[].text, faq[].question, faq[].answer, youtube_description_hook, youtube_hashtags, video_description, tags, external_links[].anchor_text, external_links[].reason, image_descriptions[].alt_text, image_descriptions[].caption, clean_transcript) MUSZĄ być napisane w 100% w języku docelowym: **{target_lang_name} ({target_lang})**, naturalnym, idiomatycznym językiem redakcyjnym.
- ⚠️ KRYTYCZNY WYJĄTEK TECHNICZNY (DUAL-LANGUAGE ANCHOR):
  Pola `chapters[].anchor_text` oraz `quotes[].anchor_text` służą do technicznego dopasowania znaczników czasu (regex/fuzzy match) bezpośrednio w oryginalnym pliku VTT!
  Dlatego `anchor_text` MUSI pozostać DOKŁADNYM, NIETŁUMACZONYM cytatem 8-15 słów w oryginalnym języku transkryptu ({source_lang}) — słowo w słowo tak, jak występuje w transkrypcie poniżej!
  Natomiast `chapters[].label` oraz `quotes[].text` MUSZĄ być w języku docelowym ({target_lang_name}).

## KOREKTA BŁĘDÓW FONETYCZNYCH ASR
- {ASR_PHONETIC_INSTRUCTION}

Na podstawie transkryptu nagrania wideo przygotuj PELNY PAKIET SEO w języku {target_lang_name} ({target_lang}).

## DANE WEJSCIOWE
Tytul: {title}
URL: {yt_url}
Czas nagrania: {total_min}:{total_sec:02d} ({total_min} minut)

Transkrypt z markerami [MM:SS]:
{text_trimmed}
{saas_section}
## KLUCZOWE ZASADY DLA ROZDZIALOW

Dla kazdego rozdzialu MUSISZ podac pole "anchor_text" \u2014 jest to DOKLADNY CYTAT 8-15 slow z transkryptu W ORYGINALNYM JĘZYKU TRANSKRYPTU ({source_lang}), ktore sa PIERWSZYMI slowami wypowiadanymi na poczatku danego tematu/rozdzialu.
Ten cytat musi byc DOKLADNIE TAKI jak w transkrypcie powyzej (dokladny tekst, male/wielkie litery bez znaczenia, BEZ TŁUMACZENIA).
NIE parafrazuj, NIE streszczaj, NIE tłumacz pola anchor_text \u2014 kopiuj dokladny fragment z transkryptu.
Natomiast pole "label" rozdzialu MUSI byc w języku docelowym: {target_lang_name} ({target_lang}).

Rozdzialy musza:
- Pokrywac CALY material od poczatku do konca (~{total_min} min)
- Byc rownomiernie rozlozone (co 3-7 minut)
- Miec {ch_range} rozdzialow (skaluj z dlugoscia materialu)
- Pierwszy zaczyna sie od samego poczatku rozmowy

## CO WYGENEROWAC (wszystkie teksty użytkowe w języku: {target_lang_name} [{target_lang}])

1. **focus_keyphrases** — Lista w języku {target_lang_name}: PIERWSZA fraza = Glowna (2-4 slowa, naturalna, wyszukiwalna w języku {target_lang_name}). POZOSTALE = Poboczne LSI (5-8 fraz, 2-5 slow, semantycznie powiazane w języku {target_lang_name}).
   ZASADY GRAMATYKI ({target_lang_name}):
   - ZAKAZ sztucznego Title Case (chyba że wymaga tego gramatyka języka {target_lang_name}, np. rzeczowniki w DE)
   - Fraza MUSI brzmiec naturalnie w języku {target_lang_name}
   - Glowna fraza MUSI pojawic sie w minimum 1 srodtytule H3
   - Frazy poboczne: w pozostalych H3 i FAQ
2. **post_title** \u2014 max 80 znakow, w języku {target_lang_name}. SEO-first tytul artykulu (tag h1). MUSI zawierac glowna focus_keyphrase. Naturalne slowa kluczowe, bez clickbaitu.
3. {seo_title_instruction} (w języku {target_lang_name})
4. **yt_title** \u2014 KRYTYCZNE ZASADY (w języku {target_lang_name}):
   - Dlugosc: 40-65 znakow (HARD MAX: 100). Optymalna dlugosc to 50-62 znaki.
   - Zacznij od tematu glownego lub nazwiska goscia (front-loading dla suggest feed).
   - MUSI byc INNY niz post_title i seo_title \u2014 inne ustawienie slow, inny ton.
   - NIE dodawaj brandingu portalu ani kanalu \u2014 YouTube dodaje kanal automatycznie.
   - NIE uzywaj ogolnikow.
   - Wybierz jeden z formatow (zadaptowany do języka {target_lang_name}):
     A \u2014 NAPIECIE:    [Nazwisko/Temat]: [akcja] \u2014 [stawka/skutek]
     B \u2014 UJAWNIENIE:  [Temat]: [co ujawnia] \u2014 [kulisy]
     C \u2014 PYTANIE:     [Pytanie intrygujące o temat/podmiot w języku {target_lang_name}]?
     D \u2014 POWER WORD:  [Mocne słowo w {target_lang_name}]: [temat] + podmiot
   - Cel: widz klika nawet nie znajac goscia z imienia.
   - KRYTYCZNE: pole yt_title NIGDY nie moze byc puste.
6. **meta_description** \u2014 max 155 znakow, z fraza kluczowa, w języku {target_lang_name}.
7. **lead** \u2014 2-3 zdania, max 300 znakow, w języku {target_lang_name}. PIERWSZE ZDANIE musi zawierac glowna fraze z focus_keyphrases[0]. To jest meta description artykulu.
8. **quotes** \u2014 {qt_range} cytatow z rozmowy:
   - "text": WYGLADZONY, CZYTELNY cytat (1-3 zdania) PRZETŁUMACZONY / ZREDAGOWANY W JĘZYKU DOCELOWYM ({target_lang_name}). Usun jakania, powtorzenia, skoryguj bledy fonetyczne ASR.
   - "speaker": imie i nazwisko (skorygowane zgodnie z tytułem i kontekstem)
   - "anchor_text": DOKLADNE 8-15 pierwszych slow ORYGINALNEGO transkryptu w języku źródłowym ({source_lang}) — BEZ TŁUMACZENIA!
10. **chapters** \u2014 {ch_range} rozdzialow:
    - "label": tytul rozdzialu (max 60 zn) w języku docelowym ({target_lang_name})
    - "anchor_text": DOKLADNY CYTAT 8-15 pierwszych slow z ORYGINALNEGO transkryptu w języku źródłowym ({source_lang}) — BEZ TŁUMACZENIA!
11. **faq** \u2014 {faq_range} pytan i odpowiedzi w języku {target_lang_name}. Naturalne, zorientowane na search intent.
12. **youtube_description_hook** \u2014 max 200 znakow, w języku {target_lang_name}. Angazujacy wstep 2-3 zdania.
    PIERWSZE zdanie MUSI zawierac glowna fraze z focus_keyphrases[0].
    Widoczne pod wideo bez klikania "Wiecej". BEZ hashtagow, BEZ linkow.
13. **youtube_hashtags** \u2014 lista dokladnie 3 hashtagow jako JSON array w języku {target_lang_name},
    np. ["#polityka", "#historia", "#Polska"]. Tylko hashtagi, nic wiecej.
14. **video_description** \u2014 max 200 zn, dla schema, w języku {target_lang_name}.
15. **tags** \u2014 5-8 tagow lowercase w języku {target_lang_name}.
16. **external_links** \u2014 lista 2-3 linkow zewnetrznych DoFollow do zrodel wysokiego autorytetu dla rynku/języka {target_lang_name}.
    Kazdy link to dict: {{"url": "...", "anchor_text": "...", "reason": "..."}}
    ZASADY:
    a) Zrodla ktore Google wysoko wazy (E-E-A-T) dla języka {target_lang_name}:
       - Preferowane autorytety: {eeat_sources}
       - YouTube (link do oryginalnego wideo: {yt_url})
    b) Linki MUSZA byc tematycznie powiazane z trescia artykulu
    c) anchor_text to naturalny tekst w języku {target_lang_name}, w ktory jest wpleciony link
    d) Nie wymyslaj URL-i \u2014 podaj REALNE adresy stron, ktore ISTNIEJA
    e) reason: krotkie uzasadnienie w języku {target_lang_name} dlaczego to zrodlo jest authority
    f) Jeden z linkow MOZE byc do oryginalnego wideo YouTube ({yt_url})
    KRYTYCZNE DLA JSON: W polach URL i anchor_text NIE uzywaj podwojnych cudzyslowow.
    Caly output to JSON \u2014 podwojne cudzysłowy wewnatrz wartosci LAMIA parsowanie.
17. **image_descriptions** \u2014 lista 2 opisow do screenshotow z wideo w języku {target_lang_name} (FALLBACK gdy SAAS Vision API niedostepny).
    Kazdy dict: {{"alt_text": "...", "caption": "...", "context": "..."}}
    ZASADY:
    a) alt_text: max 125 zn, w języku {target_lang_name}, MUSI zawierac glowna fraze z focus_keyphrases[0].
       Format: "[co widac na obrazku] - [fraza kluczowa]". Opisz scene z materialu.
    b) caption: 1 zdanie w języku {target_lang_name} opisujace scene widoczna na screenshocie z wideo.
    c) context: gdzie wstawic screenshot w article_body ("po akapicie 1" lub "po pierwszym H2").
       Pierwsza pozycja: "po akapicie 1". Druga: "po pierwszym H2" lub "przed FAQ".
18. **clean_transcript** \u2014 zredagowany stylistycznie, interpunkcyjnie i ortograficznie zapis wypowiedzi z transkryptu, podzielony na czytelne akapity (oddzielone znakami \\n\\n) z zachowaniem timestampów co akapit w formacie `[MM:SS]`, oczyszczony z błędów fonetycznych ASR (skoryguj nazwiska i nazwy własne zgodnie z tytułem filmu: {title}) oraz wypełniaczy typu 'yyy', 'eee'.

## KRYTYCZNE ZASADY FORMATU JSON I DUAL-LANGUAGE ANCHOR

Twoja odpowiedz MUSI byc poprawnym JSON. Pamietaj:
- W polach HTML (article_body) ZAWSZE uzywaj APOSTROFOW (') w atrybutach tagow HTML.
- NIGDY nie wstawiaj surowych podwojnych cudzyslowow (") wewnatrz wartosci JSON string.
- Jesli musisz uzyc cudzysłowu w tekscie, escape'uj go jako \\\".
- Poprawne: <a href='https://example.com' target='_blank'>tekst</a>
- BLEDNE: <a href="https://example.com" target="_blank">tekst</a> (LAMIE JSON!)
- PRZYPOMNIENIE DUAL-LANGUAGE ANCHOR: Wszystkie treści generuj w języku **{target_lang_name} ({target_lang})**, ALE pola `chapters[].anchor_text` oraz `quotes[].anchor_text` MUSZĄ być dokładnym, NIETŁUMACZONYM cytatem z oryginalnego transkryptu ({source_lang})!

KRYTYCZNE: Pola post_title, seo_title, yt_title MUSZA byc niepuste.
yt_title to OSOBNY, INNY tytul niz post_title \u2014 angazujacy, YouTubowy.
NIGDY nie zostawiaj ich pustych.
{pub_type_section}
Odpowiedz TYLKO JSON (bez markdown):
{{"focus_keyphrases":["fraza glowna","fraza 2","fraza 3"],"post_title":"...","seo_title":"...","yt_title":"...","meta_description":"...","lead":"...","quotes":[{{"text":"...","speaker":"...","anchor_text":"..."}}],"chapters":[{{"label":"...","anchor_text":"..."}}],"faq":[{{"question":"...","answer":"..."}}],"youtube_description_hook":"...","youtube_hashtags":["..."],"video_description":"...","tags":["..."],"external_links":[{{"url":"...","anchor_text":"...","reason":"..."}}],"image_descriptions":[{{"alt_text":"...","caption":"...","context":"..."}}],"clean_transcript":"[00:00] Zredagowany akapit 1...\\n\\n[02:15] Zredagowany akapit 2..."}}"""

    logger.info("Calling %s for: %s [type=%s, source=%s -> target=%s]", provider, title[:60], publication_type, source_lang, target_lang)
    if priority_keywords:
        logger.info(
            "SAAS enrichment active: %d keywords, %d links",
            len(priority_keywords),
            len(internal_links) if internal_links else 0,
        )
    if site_brand:
        logger.info("site_brand: %r", site_brand)
    if publication_type != "full_analysis":
        logger.info("Publication type override: %s", publication_type)
    try:
        text = _call_llm(prompt, api_key, provider)
        text = text.strip()
        text = re.sub(r"^```json\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        # D15: Pre-parse sanitization — repair broken HTML attrs before json.loads()
        text = _sanitize_llm_json(text)
        return json.loads(text)
    except json.JSONDecodeError as e:
        # D12: Log raw LLM output for debugging (first 2000 chars)
        logger.error(
            "JSON parse failed at char %d: %s\nRaw LLM output (first 2000 chars):\n%s",
            e.pos, e.msg, text[:2000]
        )

        # D12: 1 retry — ask LLM to fix the JSON
        retry_prompt = (
            "Twoja poprzednia odpowiedz zawierala blad skladni JSON "
            f"(pozycja {e.pos}: {e.msg}).\n"
            "Napraw i zwroc TYLKO poprawny JSON. "
            "UWAGA: W polach HTML (article_body) uzywaj apostrofow (') "
            "zamiast cudzyslowow (\") w atrybutach HTML, np: "
            "<a href='https://...' target='_blank'>\n\n"
            f"Oryginalna odpowiedz do naprawy:\n{text}"
        )
        logger.info("D12: Retrying LLM with fix prompt...")
        try:
            text2 = _call_llm(retry_prompt, api_key, provider)
            text2 = text2.strip()
            text2 = re.sub(r"^```json\s*", "", text2)
            text2 = re.sub(r"\s*```$", "", text2)
            # D15: Apply sanitizer on retry output too
            text2 = _sanitize_llm_json(text2)
            result = json.loads(text2)
            logger.info("D12: Retry succeeded — valid JSON obtained")
            return result
        except json.JSONDecodeError as e2:
            logger.error(
                "D12: RETRY also failed at char %d: %s\nRetry output (first 2000 chars):\n%s",
                e2.pos, e2.msg, text2[:2000]
            )
            raise
        except Exception as retry_exc:
            logger.error("D12: RETRY LLM call failed: %s", retry_exc)
            raise
    except Exception as exc:
        logger.error("%s call failed: %s", provider, exc)
        raise


# ============================================================
# KEYPHRASES NORMALIZATION (D5, vse-dev-19)
# ============================================================

def _normalize_keyphrases(result: dict) -> list[str]:
    """Normalize LLM output to always have focus_keyphrases as a list."""
    keyphrases = result.get("focus_keyphrases", [])
    if isinstance(keyphrases, list) and keyphrases:
        return [kp.strip() for kp in keyphrases if isinstance(kp, str) and kp.strip()]

    keyphrase = result.get("focus_keyphrase", "").strip()
    if keyphrase:
        return [keyphrase]

    return []

# Backward compat alias
generate_video_schema = generate_seo_v4

# ============================================================
# D13: SLUG HARD LIMIT — trim to max 60 chars at word boundary
# ============================================================

def _trim_slug(slug: str, max_len: int = 60) -> str:
    """Trim slug to max_len characters at the last full word boundary."""
    if len(slug) <= max_len:
        return slug
    trimmed = slug[:max_len].rsplit("-", 1)[0]
    return trimmed if trimmed else slug[:max_len]


# ============================================================
# JSON-LD SCHEMA BUILDER (MULTI-LANGUAGE)
# ============================================================

def build_jsonld_schemas(seo: dict, target_lang: str = "pl") -> list[dict]:
    """Build VideoObject + Clip + FAQPage JSON-LD schemas with inLanguage and localized WatchAction."""
    target_lang = (target_lang or seo.get("target_lang") or "pl").lower()[:2]
    if target_lang not in SUPPORTED_LANGUAGES:
        target_lang = "pl"
    watch_label = SUPPORTED_LANGUAGES[target_lang]["WatchAction"]

    yt_id = seo.get("youtube_id", "")
    yt_url = seo.get("yt_url", f"https://www.youtube.com/watch?v={yt_id}" if yt_id else "")
    total_dur = int(seo.get("total_duration") or seo.get("duration_seconds") or 0)
    iso_dur = seo.get("duration_iso") or format_duration_iso(total_dur)
    chapters = seo.get("chapters", [])

    clips: list[dict] = []
    for i, ch in enumerate(chapters):
        ch_time = ch.get("time", ch.get("start", 0))
        if i + 1 < len(chapters):
            next_ch = chapters[i + 1]
            end_time = next_ch.get("time", next_ch.get("start", total_dur))
        else:
            end_time = total_dur
        clips.append({
            "@type": "Clip",
            "name": ch.get("label") or ch.get("title", ""),
            "startOffset": ch_time,
            "endOffset": end_time,
            "url": f"{yt_url}&t={ch_time}s" if yt_url else "",
        })

    video_schema: dict = {
        "@context": "https://schema.org",
        "@type": "VideoObject",
        "name": seo.get("seo_title") or seo.get("post_title", ""),
        "description": seo.get("video_description") or seo.get("meta_description", ""),
        "thumbnailUrl": f"https://img.youtube.com/vi/{yt_id}/maxresdefault.jpg" if yt_id else "",
        "contentUrl": yt_url,
        "embedUrl": f"https://www.youtube.com/embed/{yt_id}" if yt_id else "",
        "duration": iso_dur,
        "inLanguage": target_lang,
        "potentialAction": {
            "@type": "WatchAction",
            "name": watch_label,
            "target": yt_url,
        },
    }
    if clips:
        video_schema["hasPart"] = clips

    schemas: list[dict] = [video_schema]

    faq_items = []
    for faq in seo.get("faq", []):
        if faq.get("question") and faq.get("answer"):
            faq_items.append({
                "@type": "Question",
                "name": faq["question"],
                "acceptedAnswer": {"@type": "Answer", "text": faq["answer"]},
            })
    if faq_items:
        schemas.append({
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "inLanguage": target_lang,
            "mainEntity": faq_items,
        })

    return schemas


# ============================================================
# PER-MATERIAL ON-DEMAND LANGUAGE ADAPTATION (KROK 2.3)
# ============================================================

def adapt_material_language(
    material_type: str,
    target_lang: str,
    source_data: dict,
    llm_provider: Optional[str] = None,
    api_key: Optional[str] = None,
) -> dict:
    """Adapt/translate a specific generated SEO material into target_lang on-demand."""
    target_lang = (target_lang or "pl").lower()[:2]
    if target_lang not in SUPPORTED_LANGUAGES:
        raise ValueError(f"Unsupported target_lang: {target_lang}")

    lang_cfg = SUPPORTED_LANGUAGES[target_lang]
    target_lang_name = lang_cfg["name"]
    provider = (llm_provider or os.getenv("LLM_PROVIDER", "gemini")).lower()

    if not api_key:
        if provider == "claude":
            api_key = os.getenv("ANTHROPIC_API_KEY", "")
        else:
            provider = "gemini"
            api_key = os.getenv("GEMINI_API_KEY", "")
            if not api_key and os.getenv("ANTHROPIC_API_KEY"):
                provider = "claude"
                api_key = os.getenv("ANTHROPIC_API_KEY", "")

    material_type = (material_type or "article").lower().strip()

    if material_type == "all":
        import concurrent.futures

        def _run_sub(m_type: str) -> tuple[dict, dict]:
            sub_tok = current_llm_usage.set({
                "input_tokens": 0,
                "output_tokens": 0,
                "last_provider": provider,
            })
            try:
                res = adapt_material_language(m_type, target_lang, source_data, provider, api_key)
                u = current_llm_usage.get() or {}
                return res, u
            finally:
                current_llm_usage.reset(sub_tok)

        sub_types = ["article", "youtube", "meta"]
        if source_data.get("quotes"):
            sub_types.append("quotes")

        combined: dict = {}
        parent_tracker = current_llm_usage.get()
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
            future_map = {m_t: ex.submit(_run_sub, m_t) for m_t in sub_types}
            for m_t in ["meta", "youtube", "article", "quotes"]:
                if m_t not in future_map:
                    continue
                try:
                    sub_res, sub_usage = future_map[m_t].result()
                    combined.update(sub_res)
                    if parent_tracker is not None:
                        parent_tracker["input_tokens"] += int(sub_usage.get("input_tokens", 0))
                        parent_tracker["output_tokens"] += int(sub_usage.get("output_tokens", 0))
                        if sub_usage.get("last_provider"):
                            parent_tracker["last_provider"] = sub_usage["last_provider"]
                except Exception as sub_exc:
                    logger.warning("adapt_material_language(all) sub-task %s failed: %s", m_t, sub_exc)

        merged_for_schema = dict(source_data)
        merged_for_schema.update(combined)
        merged_for_schema["target_lang"] = target_lang
        combined["json_ld"] = build_jsonld_schemas(merged_for_schema, target_lang=target_lang)
        combined["target_lang"] = target_lang
        combined["material_type"] = "all"
        return combined

    if material_type == "article":
        payload = {
            "post_title": source_data.get("post_title", ""),
            "lead": source_data.get("lead", ""),
            "article_body": source_data.get("article_body", ""),
            "faq": source_data.get("faq", []),
        }
        prompt = f"""Jesteś doświadczonym redaktorem SEO (native speaker języka {target_lang_name} [{target_lang}]).
Przetłumacz i zaadaptuj kulturowo oraz pod kątem SEO poniższy artykuł na język **{target_lang_name} ({target_lang})**.

ZASADY KRYTYCZNE:
1. Zachowaj DOKŁADNIE strukturę HTML w `article_body` (wszystkie tagi `<h3>`, `<p>`, `<ul>`, `<li>`, `<strong>`, `<aside>`, `<hr>`, `<a href='...'>`).
2. W atrybutach HTML używaj WYŁĄCZNIE pojedynczych apostrofów (`'`), NIGDY podwójnych cudzysłowów (`"`).
3. Zachowaj wszystkie znaczniki czasu (np. `[12:34]`, `05:20`) oraz nazwy własne i linki URL bez zmian, tłumacząc tekst wokół nich.
4. Przetłumacz również `post_title`, `lead` oraz listę `faq` (`question` i `answer`).
5. Zwróć WYŁĄCZNIE poprawny obiekt JSON z kluczami: `post_title`, `lead`, `article_body`, `faq`.

Dane wejściowe JSON:
{json.dumps(payload, ensure_ascii=False)}

Odpowiedz TYLKO poprawnym JSON (bez markdown):"""

    elif material_type == "youtube":
        chapters_in = [
            {"time": c.get("time", 0), "label": c.get("label", "")}
            for c in source_data.get("chapters", [])
        ]
        yt_body_in = (
            source_data.get("youtube_description_body")
            or source_data.get("youtube_description_hook")
            or source_data.get("video_description", "")
        )
        yt_hook_in = source_data.get("youtube_description_hook") or yt_body_in
        payload = {
            "yt_title": source_data.get("yt_title") or source_data.get("post_title", ""),
            "youtube_description_body": yt_body_in,
            "youtube_description_hook": yt_hook_in,
            "youtube_mid_cta": source_data.get("youtube_mid_cta", ""),
            "video_description": source_data.get("video_description", ""),
            "chapters": chapters_in,
            "youtube_hashtags": source_data.get("youtube_hashtags", []),
            "tags": source_data.get("tags", []),
        }
        prompt = f"""Jesteś ekspertem YouTube SEO dla rynku języka **{target_lang_name} ({target_lang})**.
Przetłumacz i zoptymalizuj pod kątem algorytmu YouTube poniższy pakiet metadanych wideo na język **{target_lang_name} ({target_lang})**.

ZASADY KRYTYCZNE:
1. `yt_title`: angażujący tytuł YouTube w języku {target_lang_name} (40-70 znaków).
2. `youtube_description_body`, `youtube_description_hook` oraz `video_description`: przetłumacz CAŁY tekst opisu na naturalny, angażujący język {target_lang_name} (nie zostawiaj żadnych zdań w języku źródłowym!).
3. `youtube_mid_cta`: przetłumacz wezwanie do subskrypcji (CTA) na naturalny język {target_lang_name} (zachowaj emotikonę 🔔 jeśli występuje).
4. `chapters`: przetłumacz każde pole `label` na język {target_lang_name}, ale ZACHOWAJ DOKŁADNIE oryginalną wartość liczbową `time` (sekundy)!
5. `youtube_hashtags` (3 hashtagi) i `tags` (5-8 tagów): zaadaptuj do popularnych fraz w języku {target_lang_name}.
6. Zwróć WYŁĄCZNIE poprawny JSON z kluczami: `yt_title`, `youtube_description_body`, `youtube_description_hook`, `youtube_mid_cta`, `video_description`, `chapters`, `youtube_hashtags`, `tags`.

Dane wejściowe JSON:
{json.dumps(payload, ensure_ascii=False)}

Odpowiedz TYLKO poprawnym JSON (bez markdown):"""

    elif material_type == "meta":
        payload = {
            "seo_title": source_data.get("seo_title", ""),
            "post_title": source_data.get("post_title", ""),
            "meta_description": source_data.get("meta_description", ""),
            "lead": source_data.get("lead", ""),
            "focus_keyphrases": source_data.get("focus_keyphrases", []),
            "tags": source_data.get("tags", []),
        }
        prompt = f"""Jesteś specjalistą Technical & On-Page SEO dla rynku języka **{target_lang_name} ({target_lang})**.
Zaadaptuj poniższe meta tagi i frazy kluczowe na język **{target_lang_name} ({target_lang})**, dobierając naturalne, wyszukiwane w Google frazy w tym języku.

ZASADY KRYTYCZNE:
1. `seo_title`: max 60 znaków w języku {target_lang_name}.
2. `post_title`: max 80 znaków w języku {target_lang_name}.
3. `meta_description`: max 155 znaków w języku {target_lang_name}, zawiera główną frazę kluczową.
4. `lead`: 2-3 zdania podsumowania w języku {target_lang_name}.
5. `focus_keyphrases`: lista naturalnych fraz kluczowych w języku {target_lang_name} (pierwsza = główna fraza 2-4 słowa).
6. `tags`: 5-8 tagów lowercase w języku {target_lang_name}.
7. Zwróć WYŁĄCZNIE poprawny JSON z kluczami: `seo_title`, `post_title`, `meta_description`, `lead`, `focus_keyphrases`, `tags`.

Dane wejściowe JSON:
{json.dumps(payload, ensure_ascii=False)}

Odpowiedz TYLKO poprawnym JSON (bez markdown):"""

    elif material_type == "quotes":
        quotes_in = [
            {
                "speaker": q.get("speaker", ""),
                "text": q.get("text", ""),
                "time": q.get("time", 0),
            }
            for q in source_data.get("quotes", [])
        ]
        payload = {"quotes": quotes_in}
        prompt = f"""Jesteś redaktorem tłumaczącym kluczowe cytaty z wywiadu na język **{target_lang_name} ({target_lang})**.
Przetłumacz pole `text` każdego cytatu na naturalny, wygładzony język **{target_lang_name} ({target_lang})**, zachowując bez zmian `speaker` oraz `time`.

Dane wejściowe JSON:
{json.dumps(payload, ensure_ascii=False)}

Zwróć WYŁĄCZNIE poprawny JSON z kluczem `quotes` (bez markdown):"""

    elif material_type == "schema":
        chapters_in = [
            {"time": c.get("time", 0), "label": c.get("label", "")}
            for c in source_data.get("chapters", [])
        ]
        payload = {
            "seo_title": source_data.get("seo_title") or source_data.get("post_title", ""),
            "video_description": source_data.get("video_description") or source_data.get("meta_description", ""),
            "chapters": chapters_in,
            "faq": source_data.get("faq", []),
        }
        prompt = f"""Przetłumacz poniższe pola danych strukturalnych Schema.org (VideoObject + Clip + FAQPage) na język **{target_lang_name} ({target_lang})**.
Zachowaj wartości liczbowe `time` w `chapters`.

Dane wejściowe JSON:
{json.dumps(payload, ensure_ascii=False)}

Zwróć WYŁĄCZNIE poprawny JSON z kluczami: `seo_title`, `video_description`, `chapters`, `faq` (bez markdown):"""

    else:
        raise ValueError(f"Unsupported material_type: {material_type}")

    raw = _call_llm(prompt, api_key, provider)
    cleaned = raw.strip()
    cleaned = re.sub(r"^```json\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = _sanitize_llm_json(cleaned)
    adapted = json.loads(cleaned)

    if material_type == "youtube":
        body_val = (
            adapted.get("youtube_description_body")
            or adapted.get("youtube_description_hook")
            or adapted.get("video_description")
            or ""
        )
        hook_val = adapted.get("youtube_description_hook") or body_val
        if body_val:
            adapted["youtube_description_body"] = body_val
        if hook_val:
            adapted["youtube_description_hook"] = hook_val

    if material_type == "meta" and "focus_keyphrases" in adapted:
        kps = adapted.get("focus_keyphrases") or []
        if isinstance(kps, list) and kps:
            adapted["focus_keyphrase"] = kps[0]

    if material_type == "schema":
        merged_seo = dict(source_data)
        merged_seo.update(adapted)
        merged_seo["target_lang"] = target_lang
        adapted["json_ld"] = build_jsonld_schemas(merged_seo, target_lang=target_lang)

    adapted["target_lang"] = target_lang
    adapted["material_type"] = material_type
    return adapted


# ============================================================
# KROK B.C: HARD ANTI-CONFABULATION BLOCK
# ============================================================

def generate_schema_without_transcript(*args, **kwargs) -> dict:
    """ZAKAZANE (KROK B.C): Nigdy nie generujemy pakietu SEO ani artykułu z samego tytułu bez transkryptu."""
    raise ValueError(
        "Brak transkryptu wideo: nie udało się pobrać napisów z YouTube "
        "(sprawdź czy działa VSE Local Runner na komputerze lub czy film posiada napisy na YouTube). "
        "Generowanie zostało zatrzymane, aby zapobiec konfabulacji AI (0 pobranych kredytów)."
    )


# ============================================================
# FULL PIPELINE — VTT → LLM → resolved chapters
# ============================================================

def process_video(
    youtube_id: str,
    wp_id: int,
    post_title: str,
    yt_url: str,
    vtt_path: Optional[str],
    api_key: str,
    out_dir: Optional[str] = None,
    sleep_between: int = 0,
    provider: str = "gemini",
    priority_keywords: Optional[list[str]] = None,
    internal_links: Optional[list[dict]] = None,
    site_brand: Optional[str] = None,
    publication_type: str = "full_analysis",
    meta: Optional[dict] = None,
    target_lang: str = "pl",
    source_lang: str = "auto",
) -> dict:
    """Run the full generation pipeline for a single video."""
    target_lang = (target_lang or "pl").lower()[:2]
    if target_lang not in SUPPORTED_LANGUAGES:
        target_lang = "pl"

    if (not source_lang or source_lang == "auto") and meta and meta.get("source_lang"):
        source_lang = meta["source_lang"]

    logger.info(
        "Processing video: %s (WP#%s) via %s [type=%s, lang=%s->%s]",
        youtube_id, wp_id, provider, publication_type, source_lang, target_lang,
    )

    # KROK B.C: Hard Anti-Confabulation Guard — vtt_path must exist and have >= 50 chars of real transcript
    if not vtt_path or not os.path.exists(vtt_path):
        raise ValueError(
            "Brak transkryptu wideo: nie udało się pobrać napisów z YouTube "
            "(sprawdź czy działa VSE Local Runner na komputerze lub czy film posiada napisy na YouTube). "
            "Generowanie zostało zatrzymane, aby zapobiec konfabulacji AI (0 pobranych kredytów)."
        )

    tracker_token = current_llm_usage.set({
        "input_tokens": 0,
        "output_tokens": 0,
        "last_provider": provider,
    })

    try:
        # Auto-detect source_lang from VTT if still unknown
        if not source_lang or source_lang == "auto":
            try:
                from core.fetcher import detect_transcript_language
                with open(vtt_path, encoding="utf-8", errors="replace") as vf:
                    raw_vtt_sample = vf.read(16000)
                source_lang = detect_transcript_language(
                    raw_vtt_sample,
                    metadata_lang=(meta or {}).get("default_audio_language"),
                )
            except Exception:
                source_lang = "pl"

        timestamped, segments, duration = parse_vtt_full(vtt_path)
        if len(timestamped.strip()) < 50:
            raise ValueError(
                "Brak transkryptu wideo: pobrany plik napisów zawiera mniej niż 50 znaków tekstu. "
                "Generowanie zostało zatrzymane, aby zapobiec konfabulacji AI (0 pobranych kredytów)."
            )

        dur_min = int(duration // 60)
        dur_sec = int(duration % 60)
        logger.info(
            "VTT parsed: %d chars | %d segments | %d:%02d | source_lang=%s | target_lang=%s",
            len(timestamped), len(segments), dur_min, dur_sec, source_lang, target_lang,
        )

        result = generate_seo_v4(
            post_title, timestamped, duration, yt_url, api_key, provider,
            priority_keywords=priority_keywords,
            internal_links=internal_links,
            site_brand=site_brand,
            publication_type=publication_type,
            target_lang=target_lang,
            source_lang=source_lang,
        )

        # KROK B.D: Ensure clean_transcript is populated (LLM-edited or rule-based fallback with [MM:SS] paragraphs)
        llm_clean_tr = (result.get("clean_transcript") or "").strip()
        if len(llm_clean_tr) >= 50:
            result["clean_transcript"] = llm_clean_tr
        else:
            result["clean_transcript"] = build_clean_transcript_from_segments(segments)

        # D5: Normalize keyphrases — always store as list
        keyphrases = _normalize_keyphrases(result)
        result["focus_keyphrases"] = keyphrases
        result["focus_keyphrase"] = keyphrases[0] if keyphrases else ""
        logger.info("focus_keyphrases: %r", keyphrases)

        # Fallback: post_title z seo_title jesli puste
        if not result.get("post_title", "").strip():
            result["post_title"] = result.get("seo_title", post_title)
            logger.warning(
                "post_title missing — fallback to seo_title: %r",
                result["post_title"][:60],
            )

        # Fallback: yt_title z post_title jesli puste
        if not result.get("yt_title", "").strip():
            result["yt_title"] = result.get("post_title", post_title)[:100]
            logger.warning(
                "yt_title missing — fallback to post_title: %r",
                result["yt_title"][:60],
            )

        # Attach original_title before Pass 2 so ASR phonetic instruction has full context
        result["original_title"] = post_title

        # D10: Log external links from LLM output
        ext_links = result.get("external_links", [])
        if ext_links:
            logger.info("D10 external_links: %d authority links generated", len(ext_links))
            for el in ext_links:
                logger.info("  -> %s (%s)", el.get("url", "?")[:60], el.get("reason", "?")[:40])
        else:
            logger.warning("D10 external_links: LLM returned 0 links (expected 2-3)")

        # D11: Log image descriptions from LLM output (fallback for SAAS Vision)
        img_descs = result.get("image_descriptions", [])
        if img_descs:
            logger.info("D11 image_descriptions: %d LLM fallback descriptions generated", len(img_descs))
            for idx, desc in enumerate(img_descs):
                logger.info("  img[%d] alt=%r ctx=%r", idx, desc.get("alt_text", "?")[:60], desc.get("context", "?"))
        else:
            logger.info("D11 image_descriptions: LLM returned 0 (SAAS primary will be used)")

        # Anchor-match chapters to exact VTT timestamps
        resolved_chapters: list[dict] = []
        for ch in result.get("chapters", []):
            anchor = ch.get("anchor_text", "")
            ts = find_anchor_in_vtt(anchor, segments)
            matched = ts >= 0
            resolved_chapters.append({
                "time": max(0, ts),
                "label": ch["label"],
                "anchor_text": anchor,
                "matched": matched,
            })
            status = f"{ts // 60:02d}:{ts % 60:02d}" if matched else "NOT FOUND"
            logger.info("  chapter [%s] %s", status, ch["label"][:50])

        resolved_chapters.sort(key=lambda x: x["time"])
        if resolved_chapters and resolved_chapters[0]["time"] != 0:
            resolved_chapters[0]["time"] = 0

        result["chapters"] = resolved_chapters

        # Anchor-match quotes
        for q in result.get("quotes", []):
            anchor = q.get("anchor_text", q.get("text", "")[:40])
            ts = find_anchor_in_vtt(anchor, segments)
            q["time"] = max(0, ts)

        # PASS 2: Article Generation
        pressai_enabled = os.getenv("USE_PRESSAI_ARTICLE_ENGINE", "false").lower() == "true"
        pressai_url = os.getenv("SAAS_API_URL") or os.getenv("PRESSAI_API_URL", "")
        pressai_token = os.getenv("SAAS_API_TOKEN") or os.getenv("PRESSAI_EXTERNAL_TOKEN") or os.getenv("EXTERNAL_API_TOKEN", "")
        
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        try:
            article_html, article_engine = loop.run_until_complete(
                generate_article_content(
                    schema=result,
                    vtt_text=timestamped,
                    publication_type=publication_type,
                    api_key=api_key,
                    provider=provider,
                    pressai_api_url=pressai_url if pressai_enabled else "",
                    pressai_token=pressai_token if pressai_enabled else "",
                    internal_links=internal_links,
                    target_lang=target_lang,
                    source_lang=source_lang,
                )
            )
            result["article_body"] = article_html
            result["article_engine"] = article_engine
            logger.info("Pass 2: article_body=%d chars engine=%s", len(article_html), article_engine)
        except Exception as e:
            logger.error("Pass 2: article generation failed: %s", e)
            result["article_body"] = result.get("article_body", "")
            result["article_engine"] = "pass1_legacy"

        # Attach metadata
        result["wp_id"] = wp_id
        result["youtube_id"] = youtube_id
        result["original_title"] = post_title
        result["yt_url"] = yt_url
        result["total_duration"] = int(duration)
        result["duration_seconds"] = int(duration)
        result["duration_iso"] = format_duration_iso(duration)
        result["llm_provider"] = provider
        result["publication_type"] = publication_type
        result["transcript_available"] = True
        result["partial_result"] = False
        result["target_lang"] = target_lang
        result["source_lang"] = source_lang
        result["json_ld"] = build_jsonld_schemas(result, target_lang=target_lang)

        # Track SAAS enrichment in result metadata
        if priority_keywords:
            result["saas_enriched"] = True
            result["saas_keywords_count"] = len(priority_keywords)
        else:
            result["saas_enriched"] = False

        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, f"{youtube_id}.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            logger.info("Saved: %s", out_path)

        if sleep_between > 0:
            time.sleep(sleep_between)

        matched_count = sum(1 for c in resolved_chapters if c.get("matched"))
        logger.info(
            "Done: %d chapters (%d/%d matched), keyphrases=%r, type=%s, saas=%s, brand=%s, ext_links=%d, img_descs=%d, lang=%s->%s",
            len(resolved_chapters), matched_count, len(resolved_chapters),
            keyphrases, publication_type,
            "enriched" if result.get("saas_enriched") else "standalone",
            site_brand or "none",
            len(ext_links),
            len(img_descs),
            source_lang,
            target_lang,
        )
        usage = current_llm_usage.get() or {}
        result["input_tokens"] = usage.get("input_tokens", 0)
        result["output_tokens"] = usage.get("output_tokens", 0)
        result["llm_provider"] = usage.get("last_provider", provider)
        result["estimated_cost_usd"] = calculate_cost_usd(
            result["llm_provider"], result["input_tokens"], result["output_tokens"]
        )
        return result
    finally:
        current_llm_usage.reset(tracker_token)
