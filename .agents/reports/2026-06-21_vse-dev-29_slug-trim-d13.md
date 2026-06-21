# Raport D13 — Slug Trim (Twardy Limit 60 zn)

**Agent:** vse-dev-29  
**Dispatch:** D13  
**Data:** 2026-06-21  
**Status:** ✅ DONE

---

## Co zostało zrobione

### Fix 1 — Twardy limit slug w kodzie

Dodano nową funkcję `_trim_slug()` w `core/generator.py` oraz wywołanie jej
w `process_video()` po odpowiedzi LLM:

```python
def _trim_slug(slug: str, max_len: int = 60) -> str:
    if len(slug) <= max_len:
        return slug
    trimmed = slug[:max_len].rsplit("-", 1)[0]
    return trimmed if trimmed else slug[:max_len]
```

W `process_video()` po fallbackach post_title/yt_title:
```python
# D13: Hard limit — wp_slug MUST NOT exceed 60 chars
raw_slug = result.get("wp_slug", "")
trimmed_slug = _trim_slug(raw_slug, max_len=60)
if trimmed_slug != raw_slug:
    logger.info("D13 slug trimmed: %r (%d zn) → %r (%d zn)", ...)
result["wp_slug"] = trimmed_slug
```

### Fix 2 — Prompt: zachowanie polskich spójników

Zaktualizowano instrukcję `wp_slug` w promptcie (punkt 5):
- Poprzednio: "bez stop-words" — LLM usuwał `i`, `w`, `z` etc.
- Teraz: "ZACHOWAJ polskie spójniki i przyimki (i, w, z, na, do, o) gdy są
  częścią frazy kluczowej"
- Przykład: `tytus-romek-i-atomek` ZOSTAJE, bo `i` to część nazwy własnej
- Naprawia false positive RankMath: "Fraza kluczowa nieznaleziona w adresie URL"

### Bugfix — resolved_channels (literow ka z oryginalnego kodu)

W `process_video()` na końcu była literowka:
```python
# BŁĄD (oryginał):
matched_count = sum(1 for c in resolved_channels if c.get("matched"))
# POPRAWNIE:
matched_count = sum(1 for c in resolved_chapters if c.get("matched"))
```
Bug powodowałby `NameError` przy każdym wywołaniu `process_video()`.

---

## Commity

| SHA | Opis |
|-----|------|
| `effdfc75` | D13: Slug twardy limit 60 zn + zachowanie polskich spójników w promptcie |
| `491e3d2a` | D13: Bugfix resolved_channels → resolved_chapters (literowka z oryginalnego kodu) |

---

## Deploy

```
git pull: OK (Fast-forward, 10 files changed)
docker compose up -d --build vse-api: OK
Container vse-api: Started
```

---

## Weryfikacja

- [x] `_trim_slug()` obecna w kodzie z docstringiem CO/PO CO/JAK
- [x] Wywołanie w `process_video()` po LLM call
- [x] Prompt zaktualizowany — polskie spójniki zachowane
- [x] Bugfix resolved_channels → resolved_chapters
- [x] Deploy na VPS — vse-api Started

---

*vse-dev-29 | video-seo-engine | 2026-06-21*
