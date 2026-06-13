# DISPATCH-VSE-DEV-01-20260613-CLAUDE-YT-TITLES

**Agent:** `vse-dev-01`  
**Od:** `vse-strateg-01`  
**Data:** 2026-06-13  
**Priorytet:** HIGH  
**Status:** OPEN  
**Zależność:** Poczekaj na raport `vse-analyst-01` (LLM tiers) przed implementacją architektury hybrydowej. Jednak punkty 1, 2, 3 możesz implementować od razu.

---

## Kontekst

Pipeline VSE działa lokalnie (Windows, playground). OAuth YouTube naprawiony (nowy token w `.env`). 4 filmy przetworzone dziś (2026-06-13). Zidentyfikowane problemy:

1. **Tytuły YouTube nie są aktualizowane** — Gemini zwraca pustą wartość `yt_title` w ~50% przypadków. Brak fallback logic.
2. **Opisy YouTube skąpe** — `build_description()` w `yt_admin.py` generuje zbyt krótki intro. User feedback: "opisy są skąpe".
3. **Brak Claude** — generator.py hard-wired na Gemini. Potrzebny switch.
4. **`post_title` i `yt_title` puste** — 2/4 filmów nie dostały zaktualizowanego tytułu WP.

---

## Zadania implementacyjne

### ZADANIE 1 — Claude provider w generator.py [PRIORYTET 1]

Dodaj obsługę Claude jako alternatywny LLM provider.

**Zmienna środowiskowa:**
```
LLM_PROVIDER=claude        # lub: gemini (domyślnie)
ANTHROPIC_API_KEY=sk-ant-...
```

**Implementacja w `core/generator.py`:**

```python
def _call_llm(prompt: str, api_key: str, provider: str = "gemini") -> str:
    """Call LLM provider with prompt, return raw text response.
    
    Supports: gemini (default), claude.
    """
    if provider == "claude":
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt}]
        )
        return msg.content[0].text
    else:  # gemini (default)
        from google import genai
        client = genai.Client(api_key=api_key)
        return client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        ).text
```

**W `generate_seo_v4()` zamień bezpośrednie wywołanie Gemini na `_call_llm()`.**

**W `process_video()` dodaj parametr `provider: str = "gemini"`** — przekazywany z CLI przez `LLM_PROVIDER` env var.

**W `cli/main.py`** dodaj odczyt `LLM_PROVIDER` i `ANTHROPIC_API_KEY` z env i przekazanie do `process_video()`.

**requirements.txt** — dodaj: `anthropic>=0.28.0`

---

### ZADANIE 2 — Naprawa `yt_title` i `post_title` [PRIORYTET 1]

Problem: Gemini czasem zwraca puste `yt_title` i `post_title`. Potrzebny robust fallback.

**W `core/generator.py` → `process_video()`** — dodaj po wywołaniu LLM:

```python
# Fallback: post_title z seo_title jeśli puste
if not result.get("post_title", "").strip():
    result["post_title"] = result.get("seo_title", post_title)
    logger.warning("post_title missing — fallback to seo_title: %r", result["post_title"][:60])

# Fallback: yt_title z post_title jeśli puste  
if not result.get("yt_title", "").strip():
    result["yt_title"] = result.get("post_title", post_title)[:100]
    logger.warning("yt_title missing — fallback to post_title: %r", result["yt_title"][:60])
```

**W prompcie** — wzmocnij instrukcję dla `yt_title` i `post_title`:
```
KRYTYCZNE: Pola post_title, seo_title, yt_title MUSZĄ być niepuste.
yt_title to OSOBNY, INNY tytul niz post_title — angazujacy, YouTubowy.
NIGDY nie zostawiaj ich pustych — to blokuje aktualizacje na YouTube.
```

---

### ZADANIE 3 — Richer YouTube descriptions [PRIORYTET 1]

Obecna struktura `build_description()` w `core/yt_admin.py` jest zbyt krótka. Rozbuduj ją:

**Nowa struktura (target: 800-1200 znaków intro przed rozdziałami):**

```
[MERYTORYCZNY WSTĘP — 3-4 zdania, z keyphrase, konkretne tezy z rozmowy]

[KLUCZOWE WĄTKI — 3-5 bullet points z najważniejszych tematów]
• Wątek 1
• Wątek 2
• Wątek 3

🔗 Pełny artykuł z transkryptem i analizą:
[wp_url]

⏱️ ROZDZIAŁY:
0:00 Intro
...

🔑 TEMATY: keyphrase • FAQ q1 • FAQ q2 • FAQ q3

[Oryginalny opis YT — zachowany]

[Footer Prawy.pl]

#hashtagi
```

**Źródło wątków:** `faq` list z SEO JSON — pierwsze 3-5 pytań przekształć w bullet points.
**Wstęp:** użyj `article_body` stripped z HTML (pierwsze 2 paragrafy) zamiast `video_description`.

Limit 4900 znaków pozostaje — dodaj truncation z logging.

---

### ZADANIE 4 — Aktualizacja YT title w inject pipeline [PRIORYTET 2]

Obecnie `inject_video()` wywołuje `update_video_title_and_description()` ale tylko jeśli OAuth skonfigurowany. Zweryfikuj i napraw:

1. Sprawdź czy `update_video_title_and_description` jest wywoływany po każdym inject
2. Dodaj explicite logowanie: `logger.info("YT title+desc update: %s -> %s", yt_id, seo.get('yt_title'))`
3. Jeśli brak OAuth — log INFO (nie ERROR), nie przerywaj
4. Zwróć `yt_update_ok` w result dict i loguj w CLI

---

## Środowisko

- Repo: `gitomwtyczka/video-seo-engine` branch `main`
- Stack: Python 3.10+, `google-genai`, `anthropic`, `requests`, `python-dotenv`
- Testy: `pytest tests/` — upewnij się że baseline przechodzi
- Odczyt/zapis: WYŁĄCZNIE przez GitHub MCP (nie lokalny klon)

## Deliverable

1. Commit(y) do branch `main` z implementacją zadań 1-4
2. Raport `2026-06-13_vse-dev-01_claude-yt-titles.md` w `.agents/reports/`
3. Dual-write raportu do `sonic-void/.agents/reports/inbox/`

Raport musi zawierać: lista commitów SHA, co zaimplementowano, co przetestowano, open issues.

---

*Dispatch by: vse-strateg-01 | 2026-06-13 20:31*
