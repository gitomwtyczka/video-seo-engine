---
dispatch_id: "VSE-DEV-22-D7-SEO-SCORING"
created: "2026-06-20"
supervisor: "Supervisor 01"
assigned_to: "[vse-dev-22]"
repo: "video-seo-engine"
branch: "main"
priority: "HIGH"
status: "dispatched"
audyt_ref: ".agents/reports/2026-06-20_vse-analyst-05_seo-audit-d7.md"
---

# DISPATCH D7 — SEO Scoring Fix (RankMath 57→90+)

## ⚡ KROK 0 — ZANIM cokolwiek zrobisz

**0. Wczytaj raport analityka:**
```
mcp_github_get_file_contents:
  owner: gitomwtyczka
  repo: video-seo-engine
  branch: main
  path: .agents/reports/2026-06-20_vse-analyst-05_seo-audit-d7.md
```
Ten raport zawiera pełną diagnozę + dokładne rekomendacje z numerami linii.

---

## Cel

RankMath daje 57/100 zamiast 90+. Napraw 6 konkretnych problemów.
**NIE dotykaj linku wewnętrznych (punkt 7) — to zależność D6b.**

## Rola: WORKER/DEV — implementacja + deploy + test

---

## Zadania w kolejności

### FAZA 1 — Quick Wins (injector.py)

#### 1.1 META description z LLM (ROOT CAUSE)

**Plik:** `core/injector.py` → `_build_rankmath_meta()`

**Problem:** LLM generuje `meta_description` z frazą kluczową (punkt 6 promptu) ale injector IGNORUJE to pole i obcina `lead` do 157 znaków.

**Fix (3 linie):**
```python
# ZAMIAST:
lead_plain = _strip_html(seo.get("lead", ""))
meta_desc = lead_plain[:157] + "..." if len(lead_plain) > 160 else lead_plain

# NOWY KOD:
meta_desc = seo.get("meta_description", "").strip()
if not meta_desc:
    lead_plain = _strip_html(seo.get("lead", ""))
    meta_desc = lead_plain[:157] + "..." if len(lead_plain) > 160 else lead_plain
```

#### 1.2 External link — usuń noreferrer

**Plik:** `core/injector.py` → `_build_external_link_block()`

**Problem:** `rel="noopener noreferrer"` — `noreferrer` może powodować że WP dodaje `nofollow`. RankMath wymaga DoFollow.

**Fix:** Zmień `rel="noopener noreferrer"` na `rel="noopener"`

#### 1.3 Sprawdź ustawienia RankMath na portalach

Zaloguj się do WP admin każdego portalu i sprawdź:
- RankMath → General Settings → Links → **"Nofollow External Links"** — musi być OFF
- RankMath → General Settings → Links → **"Open External Links in New Tab"** — sprawdź czy dodaje nofollow

Jeśli którekolwiek jest ON — zanotuj w raporcie (NIE zmieniaj sam, to decyzja usera).

### FAZA 2 — Prompt Engineering (generator.py)

#### 2.1 Gęstość keyword

**Plik:** `core/generator.py` → prompt LLM (punkt 8, article_body)

**Zmień z:**
```
8. **article_body** — HTML: 3-5 <p>, 1-2 <h2> z fraza, ~1000-1500 zn. Opisz KONKRETNE watki.
```
**Na:**
```
8. **article_body** — HTML: 3-5 <p>, 1-2 <h2> z fraza, ~1000-1500 zn. Opisz KONKRETNE watki.
   KRYTYCZNE DLA SEO: Użyj głównej frazy z focus_keyphrases[0] MINIMUM 3-5 RAZY naturalnie w tekście
   (w tym co najmniej raz w <h2>). Gęstość frazy kluczowej musi wynosić 1-1.5%.
   Nie upychaj sztucznie — fraza musi brzmieć naturalnie w kontekście zdania.
   POZYCJA: Pierwszy akapit article_body MUSI zaczynać się od zdania zawierającego
   główną frazę z focus_keyphrases[0].
```

#### 2.2 Lead z keyphrase na początku

**Plik:** `core/generator.py` → prompt LLM (punkt 7, lead)

**Zmień z:**
```
7. **lead** — 2-3 zdania, max 300 znakow, z fraza kluczowa.
```
**Na:**
```
7. **lead** — 2-3 zdania, max 300 znakow. PIERWSZE ZDANIE musi zawierać główną frazę
   z focus_keyphrases[0]. To jest meta description artykułu.
```

#### 2.3 Slug z keyphrase

**Plik:** `core/generator.py` → prompt LLM (punkt 5, wp_slug)

Wzmocnij instrukcję: `wp_slug MUSI zaczynać się od transliterowanych słów z focus_keyphrases[0]`

### FAZA 3 — Walidacja post-LLM (injector.py)

#### 3.1 Slug keyphrase validation

**Plik:** `core/injector.py` → `update_post()`

Po uzyskaniu `wp_slug`, sprawdź czy zawiera słowa z `focus_keyphrase`. Jeśli nie — override na `slugify(focus_keyphrase)`.

```python
focus_kp = seo.get("focus_keyphrase", "").strip()
if wp_slug and focus_kp:
    kp_words = set(_sanitize_slug(focus_kp).split("-"))
    slug_words = set(wp_slug.split("-"))
    if not kp_words.intersection(slug_words):
        wp_slug = _sanitize_slug(focus_kp)
        logger.warning("wp_slug overridden: keyphrase words missing → %r", wp_slug)
```

#### 3.2 Meta description keyphrase check

**Plik:** `core/injector.py` → `_build_rankmath_meta()`

Po uzyskaniu `meta_desc`, sprawdź czy zawiera chociaż jedno słowo z `focus_keyphrase`. Jeśli nie — dopisz frazę na końcu (max 160 znaków).

---

## NIE RÓB

- ❌ Linki wewnętrzne — to zależność D6b (portal musi być znany)
- ❌ Zmiana struktury plików — D6b robi refaktor architektury
- ❌ Zmiana plików profili — D6b to modyfikuje

---

## Deploy i test

1. Commit do `video-seo-engine/main` przez GitHub MCP
2. Deploy: `ssh ubuntu@147.224.162.100 "cd /home/ubuntu/video-seo-engine && git pull && docker compose -f docker-compose.vse.yml up -d --build"`
3. Przetwórz 1 film przez API i sprawdź:
   - `rank_math_description` zawiera keyphrase
   - `slug` zawiera keyphrase  
   - HTML artykułu ma link zewnętrzny bez `noreferrer`
   - Fraza pojawia się 3+ razy w article_body

---

## Raportowanie

1. `video-seo-engine/.agents/reports/2026-06-20_vse-dev-22_seo-scoring-d7.md`
2. `sonic-void/.agents/reports/inbox/2026-06-20_vse-dev-22_seo-scoring-d7.md`

---

*Supervisor 01 | video-seo-engine | 2026-06-20*
