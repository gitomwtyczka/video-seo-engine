# Raport: D1 Branding Fix + D2/D3 Struktura Artykułu

**Callsign:** vse-dev-17  
**Data:** 2026-06-19  
**Dispatch:** DISPATCH-VSE-DEV-17-20260619-PUB-QUALITY-D1D2D3  
**Status:** `done`

---

## Wyniki

### D1 — Bug: Hardcoded branding w SEO title

**Problem:** W `core/generator.py` prompt miał hardcoded `"| Prawy TV"` w instrukcji `seo_title`. Przy artykułach na kurier365 branding był zawsze Prawy TV.

**Fix zaimplementowany:**
- Dodano pole `site_brand` do obu profili YAML
- `generate_seo_v4()` otrzymał parametr `site_brand: Optional[str] = None`
- `process_video()` przyjmuje i przekazuje `site_brand` do generatora
- W prompcie: dynamiczny `| {site_brand}` jeśli podany, lub brak brandingu jeśli `None`

**Pliki zmienione:**
- `profiles/prawy.yaml` — dodano `site_brand: "Prawy TV"` | commit `5c8c228`
- `profiles/kurier365.yaml` — dodano `site_brand: "Kurier365"` | commit `9e95302`
- `core/generator.py` — site_brand param + dynamiczny prompt | commit `c3916d6`

**Weryfikacja:**
- Słowo "Prawy TV" jako literal nie występuje już w stringu promptu w `generate_seo_v4()`
- Sygnatura funkcji: `generate_seo_v4(..., site_brand: Optional[str] = None)`
- Sygnatura `process_video()`: `..., site_brand: Optional[str] = None`
- Aktywny plik: `core/generator.py` (nie `inject_rest_v5.py` — to stary standalone)

---

### D2+D3 — Restrukturyzacja artykułu + cytaty jako Podsumowanie

**Problem:** `build_post_content()` dawała kolejność:
```
lead → YT embed → Rozdziały → article_body → Kluczowe cytaty → FAQ
```
Embed YT był przed pierwszym akapitem, co dawało Google pusty fold i złe UX.

**Fix zaimplementowany:**

D2 — Nowa kolejność sekcji:
```
lead → [PIERWSZY AKAPIT article_body] → YT embed → Rozdziały → [RESZTA article_body] → Podsumowanie → FAQ → JSON-LD → JS
```

D3 — Heading sekcji cytatów: `"Kluczowe cytaty"` → `"Podsumowanie"`

**Dodane:**
- Helper `_split_first_paragraph(html)` — wyodrębnia `<p>...</p>` (DOTALL, graceful fallback)
- `intro_block` — pierwszy akapit przed embedem
- `body_rest_block` — reszta article_body po embedzie i rozdziałach

**Aktywny plik:** `core/injector.py` (zawiera `build_post_content()` — pipeline używa tego)

**Commit:** `abedcaf`

**Weryfikacja kodu:**
- `intro_block` pojawia się PRZED `embed_block` na liście `parts`
- Heading cytatów to string `"Podsumowanie"` (nie `"Kluczowe cytaty"`)
- `_split_first_paragraph()` ma docstring CO/PO CO/JAK per standard dokumentacji

---

## Commits Summary

| SHA | Plik | Zadanie |
|-----|------|---------|
| `5c8c228` | profiles/prawy.yaml | D1: site_brand: "Prawy TV" |
| `9e95302` | profiles/kurier365.yaml | D1: site_brand: "Kurier365" |
| `c3916d6` | core/generator.py | D1: remove hardcoded branding, add site_brand param |
| `abedcaf` | core/injector.py | D2+D3: first para before embed + Podsumowanie |

---

## Uwagi operacyjne

- `inject_rest_v5.py` to STARY standalone script (shadow-perihelion). NIE był edytowany — pipeline używa `core/injector.py`.
- `core/profile.py` nie wymagał zmian — profile systemu automatycznie wczytuje `site_brand` z YAML.
- `pipeline.py` (jeśli istnieje) powinien przekazać `site_brand=profile.get('site_brand')` do `process_video()` — to NEXTSTEP dla Supervisora jeśli potrzebne.
- Żadne komendy shellowe nie były uruchomione — wyłącznie GitHub MCP read/write.

---

*vse-dev-17 | video-seo-engine | 2026-06-19*
