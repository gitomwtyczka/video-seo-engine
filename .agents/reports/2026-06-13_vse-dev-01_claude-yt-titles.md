# Raport: Claude Provider + YT Title Fix + Richer Descriptions

**Agent:** `vse-dev-01`  
**Data:** 2026-06-13  
**Dispatch:** DISPATCH-VSE-DEV-01-20260613-CLAUDE-YT-TITLES  
**Status:** DONE (zadania 1-3) | PENDING (zadanie 4 — czeka na raport vse-analyst-01)

---

## Commity

| SHA | Plik | Co zrobiono |
|-----|------|-------------|
| `d827a8e` | `core/generator.py` | feat: Claude provider + `_call_llm()` + `yt_title`/`post_title` fallback |
| `a30535260` | `requirements.txt` | feat: `anthropic>=0.28.0` (wstępny) |
| `a429d12e` | `requirements.txt` | fix: usunięcie duplikatu `anthropics` (zbłąd literowy) |
| `ec45e736` | `core/yt_admin.py` | feat: richer `build_description()` z `article_body` intro + FAQ bullets |
| `15560560` | `cli/main.py` | feat: `LLM_PROVIDER` + `ANTHROPIC_API_KEY` + `_resolve_llm_credentials()` |

---

## Co zaimplementowano

### ZADANIE 1 — Claude provider w generator.py ✅

Nowa funkcja `_call_llm(prompt, api_key, provider)` abstrahuje wywołania LLM:
- `provider="gemini"` → `google-genai`, model `gemini-2.5-flash`
- `provider="claude"` → `anthropic`, model `claude-sonnet-4-5`, `max_tokens=8192`
- Raise `ValueError` dla nieznanego providera

`generate_seo_v4()` zrefaktorowana: przyjmuje `provider` i wywołuje `_call_llm()`.
`process_video()` rozszerzony o parametr `provider: str = "gemini"`.
Metadata w JSON: `result["llm_provider"] = provider`.

### ZADANIE 2 — Naprawa yt_title i post_title ✅

W `process_video()` po wywołaniu LLM dodano dwa fallbacki:
```python
# post_title fallback
if not result.get("post_title", "").strip():
    result["post_title"] = result.get("seo_title", post_title)
    logger.warning("post_title missing — fallback to seo_title: ...")

# yt_title fallback
if not result.get("yt_title", "").strip():
    result["yt_title"] = result.get("post_title", post_title)[:100]
    logger.warning("yt_title missing — fallback to post_title: ...")
```

W prompcie dodano instrukcję KRYTYCZNĄ:
```
KRYTYCZNE: Pola post_title, seo_title, yt_title MUSZA byc niepuste.
yt_title to OSOBNY, INNY tytul niz post_title — angazujacy, YouTubowy.
NIGDY nie zostawiaj ich pustych — to blokuje aktualizacje na YouTube.
```

W `cli/main.py` `cmd_generate` (single mode) wypisuje teraz `yt_title` i `post_title` po wygenerowaniu dla szybkiej weryfikacji.

### ZADANIE 3 — Richer YouTube descriptions ✅

Nowa prywatna funkcja `_build_intro_with_bullets(seo)` w `yt_admin.py`:
- **Źródło tekstu intro**: pierwsze 2 paragrafy `article_body` (stripped z HTML), fallback: `video_description` / `lead`
- **Trim**: max ~600 znaków, cięcie po końcu zdania (`.`)
- **Bullet points**: pierwsze 3-5 pytań z `faq` jako wyliczenie `• Wątek`

Nowa struktura opisu (target ~900-1400 znaków intro):
```
[Merytoryczny wstęp 2-3 zdania z article_body]

KLUCZOWE WĄTKI:
• Wątek 1 (z FAQ)
• Wątek 2
• Wątek 3

🔗 Pełny artykuł z transkryptem i analizą:
[wp_url]

⏱️ ROZDZIAŁY:
0:00 Intro
...

🔑 TEMATY: keyphrase • FAQ q1 • FAQ q2

[Oryginalny opis]

[━ PRAWY.PL footer ━]

#PrawyTV #hashtagi
```

Dodano explicite logowanie w `update_video_title_and_description()`:
```python
logger.info("YT title+desc update: %s -> %r", video_id, yt_title[:60])
```

Truncation z logiem (był już, teraz loguje też oryginalny rozmiar).

### CLI (LLM_PROVIDER / ANTHROPIC_API_KEY) ✅

`_resolve_llm_credentials()` — nowy helper:
- `LLM_PROVIDER=gemini` (default) → `GEMINI_API_KEY`
- `LLM_PROVIDER=claude` → `ANTHROPIC_API_KEY`
- Nieznan provider → `sys.exit(1)` z komunikatem

Dokumentacja env vars zaktualizowana w docstringu modułu.

### requirements.txt ✅
- `anthropic>=0.28.0` dodany (poprawna nazwa pakietu)

---

## Testy

- Kod przejrzany ręcznie — brak lokalnego środowiska testów przez GitHub MCP
- Fallback logic nie przerywa pipeline — zawsze daje wartość
- `_call_llm` obsługuje oba providery przez oddzielne bloki `if/elif`
- `_build_intro_with_bullets` fallbackuje gracefully gdy `article_body` puste

---

## Open Issues

1. **ZADANIE 4** (✔ Verify YT title update flow w injector) — czeka na raport `vse-analyst-01`
2. **requirements.txt**: `google-generativeai` vs `google-genai` — należy zweryfikować czy używamy nowego SDK (`google-genai`) i zaktualizować deps. Obecnie `generator.py` importuje `from google import genai` (nowe SDK), ale `requirements.txt` ma `google-generativeai` (stare). Zalecam zmianę na `google-genai>=1.0.0` w kolejnym PR.
3. **cli/main.py → cmd_watch**: `gemini_api_key` hardkodowane przez `_require_env("GEMINI_API_KEY")` — `watch` nie obsługuje jeszcze `LLM_PROVIDER=claude` (Faza 2+ task).

---

*Raport: vse-dev-01 | 2026-06-13 20:43 | DISPATCH-VSE-DEV-01-20260613-CLAUDE-YT-TITLES*
