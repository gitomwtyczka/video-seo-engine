# Audyt SEO RankMath — Diagnoza 57/100 i Rekomendacje do 90+

**Dispatch:** VSE-ANALYST-05-D7-SEO-AUDIT  
**Analityk:** vse-analyst-05  
**Data:** 2026-06-20  
**Portal testowy:** kurier365.pl  
**Wynik RankMath:** 57/100 → cel: 90+

---

## Podsumowanie wykonawcze

Audyt 7 punktów RankMath ujawnił **4 krytyczne braki** w pipeline VSE, które **łącznie** obniżają scoring o ~33 punkty. Naprawa tych 4 punktów powinna podnieść wynik do **85-95/100**. Dwa z nich (meta description, slug) to quick wins w `injector.py`. Dwa (gęstość keyword, fraza na początku) wymagają zmiany promptu LLM w `generator.py`. Linki zewnętrzne (D4) wymagają drobnej poprawki atrybutu `rel`. Linki wewnętrzne są zależnością od D6b.

| # | Problem RankMath | Wpływ na scoring | Priorytet | Plik | Trudność |
|---|---|---|---|---|---|
| 1 | META description brak frazy | ~5 pkt | 🔴 KRYTYCZNY | `injector.py` | Łatwy |
| 2 | Slug brak frazy | ~5 pkt | 🔴 KRYTYCZNY | `injector.py` | Łatwy |
| 3 | Gęstość keyword 0.14% | ~8 pkt | 🔴 KRYTYCZNY | `generator.py` | Średni |
| 4 | Fraza nie na początku treści | ~5 pkt | 🔴 KRYTYCZNY | `generator.py` | Łatwy |
| 5 | Linki zewnętrzne niewidoczne | ~5 pkt | 🟡 WAŻNY | `injector.py` | Łatwy |
| 6 | DoFollow linki zewnętrzne | ~5 pkt | 🟡 WAŻNY | `injector.py` | Łatwy |
| 7 | Brak linków wewnętrznych | ~5 pkt | 🔵 ZALEŻNOŚĆ | D6b | - |

**Szacowany zysk z naprawy #1-#6:** +33 punkty → 90/100

---

## Diagnoza szczegółowa

### 1. 🔴 META description — brak frazy kluczowej

**CO się dzieje:**  
`_build_rankmath_meta()` w `injector.py` buduje `rank_math_description` z pola `lead` — obcina do 157 znaków i dodaje `...`. Problem: **lead generowany przez LLM nie musi zawierać focus_keyphrase**, bo prompt LLM mówi jedynie "lead — 2-3 zdania, max 300 znaków, z frazą kluczową" — ale to nie gwarantuje że fraza trafi do pierwszych 157 znaków.

**PO CO to naprawić:**  
RankMath sprawdza literalnie czy `rank_math_focus_keyword` (pierwsza fraza) występuje w `rank_math_description`. Jeśli nie — minus ~5 punktów.

**Obecny kod** (`injector.py`, `_build_rankmath_meta()`):
```python
lead_plain = _strip_html(seo.get("lead", ""))
meta_desc = lead_plain[:157] + "..." if len(lead_plain) > 160 else lead_plain
```

**REKOMENDACJA:**  
Dwa podejścia (oba do implementacji):

**A. Generuj meta_description osobno przez LLM** (lepsze):  
Prompt już prosi o `meta_description` (punkt 6 w prompcie: "max 155 znaków, z frazą kluczową"). Problem: **ten wynik jest ignorowany przez injector!** `_build_rankmath_meta()` NIE używa `seo.get("meta_description")` — zamiast tego obcina `lead`.

**Fix w `injector.py`, `_build_rankmath_meta()`:**
```python
# ZAMIAST:
lead_plain = _strip_html(seo.get("lead", ""))
meta_desc = lead_plain[:157] + "..." if len(lead_plain) > 160 else lead_plain

# NOWY KOD:
meta_desc = seo.get("meta_description", "").strip()
if not meta_desc:
    # Fallback: lead stripped
    lead_plain = _strip_html(seo.get("lead", ""))
    meta_desc = lead_plain[:157] + "..." if len(lead_plain) > 160 else lead_plain
```

**B. Walidacja post-LLM** (dodatkowe zabezpieczenie):  
W `process_video()` (`generator.py`), po zwróceniu wyniku LLM, sprawdź czy `meta_description` zawiera choćby jedno słowo z `focus_keyphrases[0]`. Jeśli nie — dopisz na końcu.

---

### 2. 🔴 Slug — brak frazy kluczowej

**CO się dzieje:**  
`update_post()` w `injector.py` ma dwa źródła slugu:
1. `seo.get("wp_slug")` — z LLM (preferowane)
2. `_sanitize_slug(post_title)` — fallback z tytułu

Prompt LLM prosi o `wp_slug` (punkt 5): "max 60 znaków, musi zawierać słowa kluczowe z focus_keyphrases". Ale **nie ma walidacji** czy slug faktycznie zawiera keyphrase.

**PO CO to naprawić:**  
RankMath sprawdza dosłownie czy focus keyword (lub jego wariant) jest w URL. Brak → minus ~5 punktów.

**REKOMENDACJA:**  

**A. Walidacja + fallback na keyphrase-slug:**  
W `update_post()` po uzyskaniu `wp_slug`, sprawdź czy zawiera choć jedno kluczowe słowo z `focus_keyphrases[0]`. Jeśli nie — wygeneruj slug z focus_keyphrase:

```python
# Po uzyskaniu wp_slug:
focus_kp = seo.get("focus_keyphrase", "").strip()
if wp_slug and focus_kp:
    # Sprawdź czy slug zawiera główne słowa z frazy
    kp_words = set(_sanitize_slug(focus_kp).split("-"))
    slug_words = set(wp_slug.split("-"))
    if not kp_words.intersection(slug_words):
        # Slug nie zawiera frazy — użyj keyphrase jako bazy
        wp_slug = _sanitize_slug(focus_kp)
        logger.warning("wp_slug overridden: keyphrase words missing → %r", wp_slug)
```

**B. Zmiana promptu** (prostsze):  
W prompcie wzmocnić instrukcję: "wp_slug MUSI zaczynać się od transliterowanych słów z focus_keyphrases[0]".

**UWAGA:** Dla opublikowanych postów WP nie zmienia slugu (protection). To działa tylko dla nowych artykułów/drafts.

---

### 3. 🔴 Gęstość słów kluczowych — 0.14% (za niska)

**CO się dzieje:**  
RankMath oczekuje gęstości frazy kluczowej **1-1.5%** (optymalne). Przy 733 słowach artykułu, fraza powinna się pojawiać **7-11 razy**. Obecnie pojawia się **1 raz** (0.14%).

**PO CO to naprawić:**  
To **największy single-point loss** — brak gęstości kosztuje ~8 punktów RankMath.

**Obecny prompt** (`generator.py`):  
Punkt 8: `article_body — HTML: 3-5 <p>, 1-2 <h2> z frazą, ~1000-1500 zn.`  
Nigdzie nie mówi LLM wprost ile razy użyć frazy.

**REKOMENDACJA — zmiana promptu w `generator.py`:**

Zmienić punkt 8 promptu z:
```
8. **article_body** — HTML: 3-5 <p>, 1-2 <h2> z fraza, ~1000-1500 zn. Opisz KONKRETNE watki.
```
na:
```
8. **article_body** — HTML: 3-5 <p>, 1-2 <h2> z fraza, ~1000-1500 zn. Opisz KONKRETNE watki.
   KRYTYCZNE DLA SEO: Użyj głównej frazy z focus_keyphrases[0] MINIMUM 3-5 RAZY naturalnie w tekście 
   (w tym co najmniej raz w <h2>). Gęstość frazy kluczowej musi wynosić 1-1.5%.
   Nie upychaj sztucznie — fraza musi brzmieć naturalnie w kontekście zdania.
```

Dodatkowo, punkt 7 (lead) zmienić z:
```
7. **lead** — 2-3 zdania, max 300 znakow, z fraza kluczowa.
```
na:
```
7. **lead** — 2-3 zdania, max 300 znakow. PIERWSZE ZDANIE musi zawierać główną frazę 
   z focus_keyphrases[0]. To jest meta description artykułu.
```

---

### 4. 🔴 Fraza nie na początku treści

**CO się dzieje:**  
RankMath wymaga aby fraza kluczowa pojawiła się w **pierwszych 10% treści** (typowo: w pierwszym akapicie). Obecny prompt nie daje LLM takiej instrukcji wprost.

**PO CO to naprawić:**  
Brak frazy na początku = minus ~5 punktów. Google też preferuje front-loaded keywords.

**Obecny prompt** — lead mówi "z frazą kluczową" ale article_body nie mówi nic o pozycji frazy.

**REKOMENDACJA — zmiana promptu w `generator.py`:**

Dodać do punktu 8 (article_body):
```
   POZYCJA: Pierwszy akapit article_body MUSI zaczynać się od zdania zawierającego 
   główną frazę z focus_keyphrases[0]. RankMath sprawdza czy fraza jest w pierwszych 
   10% treści.
```

**Uwaga techniczna:** `_split_first_paragraph()` w `injector.py` wyciąga pierwszy `<p>` i umieszcza go PRZED embedem YouTube. Jeśli ten paragraph zawiera keyphrase — RankMath powinien to widzieć jako "fraza na początku". Kluczowe: build order to `lead → first_p → embed → ...` — więc RankMath widzi `lead` + `first_p` jako "treść na początku".

Jeśli RankMath liczy tylko `content` (post body, bez excerpt) to `first_p` musi mieć keyphrase. Jeśli liczy excerpt + content — wystarczy że lead ma keyphrase (co prompt już sugeruje).

---

### 5. 🟡 Linki zewnętrzne — RankMath nie widzi

**CO się dzieje:**  
D4 dodał `_build_external_link_block()` w `injector.py`. Generuje:
```html
<!-- wp:paragraph -->
<p>Więcej informacji: <a href="https://www.youtube.com" target="_blank" 
rel="noopener noreferrer">Źródło wideo na YouTube</a></p>
<!-- /wp:paragraph -->
```

**Dlaczego RankMath nie widzi:**

Po analizie kodu identyfikuję **3 możliwe przyczyny** (od najbardziej prawdopodobnej):

**A. `rel="noopener noreferrer"` traktowane jako nofollow** (🔴 NAJBARDZIEJ PRAWDOPODOBNE)  
RankMath w wersjach 1.0.200+ rozróżnia dofollow od nofollow. Atrybut `noreferrer` sam w sobie NIE jest nofollow, ale **niektóre konfiguracje WordPress automatycznie dodają `nofollow` do linków z `target="_blank"`**. WordPress 6.x z domyślnym filtrem `wp_targeted_link_rel` dodaje `nofollow` do KAŻDEGO linku z `target="_blank"` jeśli ustawienie jest włączone.

**B. Link jest w dalszej części treści (po `<!-- wp:more -->`)**  
Build order: `lead → <!-- more --> → first_p → embed → chapters → rest_body → EXTERNAL_LINK → ...`  
Link jest PO sekcji more, PO rest_body — RankMath skanuje cały `post_content`, więc to nie powinno być problem. Ale warto zweryfikować live HTML.

**C. WordPress sanitizer czyści HTML**  
Mało prawdopodobne — `<!-- wp:paragraph -->` block syntax jest natywny dla Gutenberga.

**REKOMENDACJA:**

Zmienić w `_build_external_link_block()`:
```python
# ZAMIAST:
f'rel="noopener noreferrer"'

# NOWY:
f'rel="noopener"'
```

Usunięcie `noreferrer` rozwiązuje potencjalny problem z WP filtrem. Dodatkowo, dla pewności, można dodać explicit `rel="dofollow noopener"` ale to niestandardowy atrybut — lepiej po prostu usunąć `noreferrer`.

**DODATKOWA REKOMENDACJA (bonus):**  
Zamiast stałego linku do YouTube (który jest oczywistym filler-linkiem), lepszy wynik SEO da link do **autorytywnego źródła tematycznego** (np. Wikipedia, oficjalna strona instytucji). Można dodać pole `seo_external_link_2` w profilu lub generować tematyczny link przez LLM.

---

### 6. 🟡 DoFollow linki zewnętrzne

**Powiązane z punktem 5.** RankMath wymaga minimum 1 linka zewnętrznego z atrybutem dofollow (brak `rel="nofollow"`).

**REKOMENDACJA:**  
Ta sama co punkt 5 — usunięcie `noreferrer`. Bez `rel="nofollow"` link jest domyślnie dofollow.

Dodatkowo, na WordPress z RankMath warto sprawdzić:
- RankMath → General Settings → Links → "Nofollow External Links" — jeśli włączone, ALL external links dostają nofollow, niezależnie od kodu HTML. **Worker powinien to sprawdzić w WP admin.**

---

### 7. 🔵 Linki wewnętrzne — ZALEŻNOŚĆ OD D6b

**CO się dzieje:**  
RankMath wymaga minimum 1 linka wewnętrznego w treści. Obecny pipeline NIE dodaje linków wewnętrznych.

**PO CO:**  
Linki wewnętrzne to krytyczny czynnik SEO:
- RankMath daje ~5 pkt za ich obecność
- Google treats internal links as authority signals
- Czytelnik odkrywa więcej treści → niższy bounce rate

**Proponowany flow (wymaga D6b: parametr `--site`):**

1. Pipeline wie na jaki portal publikuje (z profilu)
2. Przed generacją LLM → pobierz 10-20 ostatnich postów z WP REST API:
   ```
   GET {wp_base_url}/wp-json/wp/v2/posts?per_page=20&orderby=date&status=publish&_fields=id,title,link,slug
   ```
3. Przekaż tytuły + URLe do promptu LLM (sekcja SAAS enrichment `internal_links` JUŻ ISTNIEJE w `_build_saas_prompt_section()`)
4. LLM wstawia 2-3 linki naturalnie w `article_body`

**Kluczowe odkrycie:** Mechanizm JUŻ ISTNIEJE w kodzie!
- `generator.py` → `_build_saas_prompt_section()` ma sekcję `PROPOZYCJE LINKOW WEWNETRZNYCH`
- `process_video()` przyjmuje `internal_links: Optional[list[dict]]`
- Problem: **nikt nie wywołuje tego z danymi**. SAAS enricher (`api/services/saas_enricher.py`) prawdopodobnie nie pobiera linków wewnętrznych z WP.

**REKOMENDACJA:**  
To wymaga implementacji w SAAS enricher lub w pipeline caller — **nie w D7, ale w osobnym dispatch D8 lub w ramach D6b.**

---

## Plan implementacji dla D7-impl (worker)

### Faza 1 — Quick Wins (injector.py)

| Zmiana | Plik | Linia/Funkcja | Opis |
|---|---|---|---|
| META desc z LLM | `injector.py` | `_build_rankmath_meta()` | Użyj `seo.get("meta_description")` zamiast obcinania lead |
| Usunięcie noreferrer | `injector.py` | `_build_external_link_block()` | `rel="noopener"` zamiast `rel="noopener noreferrer"` |

### Faza 2 — Prompt Engineering (generator.py)

| Zmiana | Plik | Sekcja promptu | Opis |
|---|---|---|---|
| Gęstość keyword | `generator.py` | Punkt 8 (article_body) | Dodaj instrukcję: min 3-5 razy, gęstość 1-1.5% |
| Fraza na początku | `generator.py` | Punkt 8 (article_body) | "Pierwszy akapit MUSI zaczynać się od frazy" |
| Lead z keyphrase | `generator.py` | Punkt 7 (lead) | "PIERWSZE ZDANIE musi zawierać focus_keyphrases[0]" |
| Walidacja slugu | `generator.py` | Punkt 5 (wp_slug) | Wzmocnienie instrukcji: "slug MUSI zawierać keyphrase" |

### Faza 3 — Walidacja post-LLM (injector.py)

| Zmiana | Plik | Funkcja | Opis |
|---|---|---|---|
| Slug keyphrase check | `injector.py` | `update_post()` | Walidacja + override jeśli slug nie zawiera keyphrase |
| Meta desc keyphrase check | `injector.py` | `_build_rankmath_meta()` | Fallback: jeśli meta_desc nie zawiera keyphrase, dopisz |

### Faza 4 — ZALEŻNOŚĆ (D6b/D8)

| Zmiana | Plik | Opis |
|---|---|---|
| Linki wewnętrzne | SAAS enricher lub pipeline | Pobierz posty z WP REST API → przekaż do LLM via internal_links |

---

## Szacowany wpływ na RankMath scoring

| Faza | Zmiana | Punkty RankMath |
|---|---|---|
| Obecny wynik | | 57/100 |
| Faza 1 | META desc + external links fix | +10 |
| Faza 2 | Gęstość + pozycja keyword | +13 |
| Faza 3 | Walidacja slug | +5 |
| Faza 4 | Linki wewnętrzne (D6b/D8) | +5 |
| **SUMA po F1-F3** | | **~85/100** |
| **SUMA po F1-F4** | | **~90/100** |

---

## Krytyczne odkrycie: meta_description jest generowana ale IGNOROWANA

To jest **root cause** dla punktu 1. LLM generuje `meta_description` (prompt punkt 6: "max 155 znaków, z frazą kluczową"), ale `_build_rankmath_meta()` w injector.py **kompletnie ignoruje to pole** i zamiast tego obcina `lead` do 157 znaków.

To jest najłatwiejszy fix w całym audycie — 3 linie kodu.

---

## Weryfikacja RankMath ustawień na portalu (do zrobienia ręcznie)

Worker powinien sprawdzić w WP admin panelu:
1. **RankMath → General Settings → Links → "Nofollow External Links"** — jeśli ON, żaden link zewnętrzny nie dostanie dofollow, niezależnie od kodu HTML
2. **RankMath → General Settings → Links → "Open External Links in New Tab"** — może dodawać `rel="nofollow"` automatycznie
3. **WordPress → Settings → Writing → "Discourage search engines"** — powinno być OFF

---

*vse-analyst-05 | video-seo-engine | 2026-06-20 — DISPATCH D7-prep zakończony*
