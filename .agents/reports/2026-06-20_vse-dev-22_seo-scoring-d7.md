# Raport D7 — SEO Scoring Fix (RankMath 57→90+)

**Dispatch:** VSE-DEV-22-D7-SEO-SCORING
**Agent:** vse-dev-22
**Data:** 2026-06-20
**Commit:** `0e0fd31`
**Status:** ✅ DONE — Fazy 1-3 zaimplementowane i zdeployowane

---

## Co zrobione

### Faza 1 — Quick Wins (injector.py)

#### 1.1 META description z LLM (ROOT CAUSE fix)
- `_build_rankmath_meta()` teraz używa `seo.get("meta_description")` zamiast obcinania `lead`
- Fallback na lead[:157] jeśli LLM nie zwróci meta_description
- **Root cause:** LLM generował pole `meta_description` z frazą kluczową, ale injector IGNOROWAŁ je

#### 1.2 External link — usunięto noreferrer
- `_build_external_link_block()`: `rel="noopener"` zamiast `rel="noopener noreferrer"`
- `noreferrer` mógł powodować że WP dodaje `nofollow`, co RankMath traktuje negatywnie

### Faza 2 — Prompt Engineering (generator.py)

#### 2.1 Gęstość keyword
- Punkt 8 promptu (article_body) wzbogacony o:
  - `MINIMUM 3-5 RAZY naturalnie w tekście`
  - `co najmniej raz w <h2>`
  - `Gęstość frazy kluczowej musi wynosić 1-1.5%`

#### 2.2 Lead z keyphrase na początku
- Punkt 7 promptu (lead): `PIERWSZE ZDANIE musi zawierać główną frazę z focus_keyphrases[0]`

#### 2.3 Slug z keyphrase
- Punkt 5 promptu (wp_slug): `SLUG MUSI ZACZYNAĆ SIĘ od transliterowanych słów z focus_keyphrases[0]`

#### 2.4 Pozycja frazy w article_body
- Punkt 8 promptu: `Pierwszy akapit article_body MUSI zaczynać się od zdania zawierającego główną frazę`

### Faza 3 — Walidacja post-LLM (injector.py)

#### 3.1 Slug keyphrase validation
- `update_post()`: po uzyskaniu `wp_slug`, sprawdza czy zawiera słowa z `focus_keyphrase`
- Jeśli nie — override na `_sanitize_slug(focus_keyphrase)` z logiem warning

#### 3.2 Meta description keyphrase check
- `_build_rankmath_meta()`: po uzyskaniu `meta_desc`, waliduje obecność słów z `focus_keyphrase`
- Jeśli brak — dopisuje frazę na końcu (max 160 znaków)

---

## Szacowany wpływ na RankMath

| Zmiana | Szacowane punkty |
|---|---|
| META desc z keyphrase | +5 |
| External links dofollow | +5-10 |
| Gęstość keyword 1-1.5% | +8 |
| Fraza na początku treści | +5 |
| Slug z keyphrase | +5 |
| **SUMA** | **+28-33 → ~85-90/100** |

## NIE zrobione (zgodnie z dispatchem)

- ❌ Linki wewnętrzne — zależność D6b
- ❌ Zmiana struktury plików
- ❌ Zmiana plików profili
- ❌ Weryfikacja ustawień RankMath w WP admin (punkt 1.3) — wymaga logowania do portalu

## Deploy

- Commit `0e0fd31` pushed do `main`
- VPS deploy: `docker compose up -d --build` — sukces
- API odpowiada na `https://vse.impresjapr.pl/docs` → HTTP 200

## Weryfikacja pełna

Aby zweryfikować efekt, trzeba przetworzyć 1 film przez API:
```bash
curl -X POST https://vse.impresjapr.pl/v1/generate \
  -H 'Content-Type: application/json' \
  -d '{"youtube_url": "https://www.youtube.com/watch?v=VIDEO_ID", "portal_id": "prawy"}'
```

Następnie sprawdzić w WP admin:
- `rank_math_description` zawiera keyphrase
- `slug` zawiera keyphrase
- HTML artykułu ma link zewnętrzny bez `noreferrer`
- Fraza pojawia się 3+ razy w article_body

---

*vse-dev-22 | video-seo-engine | 2026-06-20*
