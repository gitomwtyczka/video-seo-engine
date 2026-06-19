# Audit: Schema.org & RankMath Multi-Keyword — vse-analyst-03

**Data:** 2026-06-19  
**Agent:** `vse-analyst-03`  
**Dispatch:** DISPATCH-VSE-ANALYST-03-20260619-SCHEMA-RANKMATH.md  
**Scope:** core/injector.py + core/generator.py + inject_rest_v5.py + RankMath API docs

---

## A1: Schema.org

### Gdzie trafia schema?

**Odpowiedz: RAW content posta — NIE do RankMath meta.**

W `core/injector.py` funkcja `build_post_content()` generuje pelny post HTML jako Gutenberg blocks. Kazdy schema dict z `build_schema_jsonld()` jest wstrzykiwany jako:

```html
<!-- wp:html -->
<script type="application/ld+json">
{ ...schema JSON... }
</script>
<!-- /wp:html -->
```

Schema **nie jest** ustawiana przez:
- `yoast_head_json` — brak w kodzie
- `rank_math_schema_data` — brak w kodzie
- Standardowe WP REST `meta` field dla schema — brak

Schema trafia do body posta jako raw block. Google crawluje ja z body — to poprawna technicznie sciezka.

---

### VideoObject — kompletnosc pol

**Status: OK — wszystkie wymagane pola sa wypelnione.**

| Pole | Status | Zrodlo |
|------|--------|--------|
| `name` | OK zawsze | `seo.get("seo_title", "")` |
| `description` | OK zawsze | `seo.get("video_description", "")` |
| `thumbnailUrl` | OK zawsze | hardcoded YT maxresdefault URL |
| `uploadDate` | OK z TZ | pobierane z WP REST, timezone append |
| `contentUrl` | OK zawsze | `seo.get("yt_url", ...)` |
| `embedUrl` | OK zawsze | `https://www.youtube.com/embed/{yt_id}` |
| `duration` | OK ISO 8601 | z VTT parser, format_duration_iso() |
| `hasPart` (Clip) | OK jesli rozdzialy | z resolved chapters |
| `interactionStatistic` | WARUNKOWE | tylko jesli YT_API_KEY jest ustawiony |

**Uwaga na `interactionStatistic`:** Pole jest opcjonalne wg Google 2026, ale podnosi score w Rich Results. Gdy `YT_API_KEY` nie jest ustawiony — pole jest pominiete.

**Uwaga na `inject_rest_v5.py` (legacy):**
Legacy skrypt ma blad w `interactionStatistic.interactionType` — uzywa `http://schema.org/WatchAction` zamiast poprawnego `https://schema.org/WatchAction`. `core/injector.py` ma to poprawione.

---

### Potencjalny KONFLIKT: dwa VideoObject na stronie

**RYZYKO WYSOKIE — do weryfikacji przez Supervisora**

VSE wstrzykuje pelny VideoObject schema w body posta.
Jednoczesnie RankMath generuje swoj wlasny VideoObject jesli:
- Ma wlaczone "Auto-detect Video" w ustawieniach
- Post ma osadzony YouTube embed (a VSE go dodaje!)

Dwa VideoObject na jednej stronie = Google traktuje to jako duplikat schema.
Efekt: warning w Google Search Console, potencjalnie ignorowanie jednego z nich.

**Rekomendacja:** Wylacz generowanie VideoObject przez RankMath dla postow VSE, lub zweryfikuj w Google Rich Results Test.

Weryfikacja: sprawdzic strone w https://search.google.com/test/rich-results — czy sa dwie deklaracje VideoObject.

---

### Quotation schema — status

**Rekomendacja: USUNAC z nowych generacji — zachowac na istniejacych postach.**

**Analiza:**
- `core/injector.py` — `build_schema_jsonld()`: Quotation jest generowana dla kazdego wpisu w `seo.get("quotes", [])`, jeden blok JSON-LD per cytat
- Docstring w kodzie: "Quotation schema is kept for completeness; Google does not render it. Do NOT add new Quotation items — preserve existing if already injected."
- Google oficjalnie NIE renderuje Quotation w rich results
- Quotation dodaje zbedny payload — kazdy post ma 2-5 cytatow = 2-5 dodatkowych JSON-LD blocks

**Gdzie w kodzie usunac:**
- `core/injector.py` > funkcja `build_schema_jsonld()` > sekcja `# Quotation — kept for completeness`
- Petla: `for q in seo.get("quotes", []):` + append Quotation dict
- Wystarczy usunac te petle (~10 linii). Docstring jest juz zaktualizowany.

---

## A2: RankMath API — Multiple Focus Keywords

### Endpoint i format

VSE uzywa dedykowanego endpointu RankMath (NIE standardowego WP REST `meta`):

```
POST {wp_base_url}/wp-json/rankmath/v1/updateMeta
{
  "objectType": "post",
  "objectID": wp_id,
  "meta": {
    "rank_math_focus_keyword": "fraza1",
    "rank_math_description": "...",
    "rank_math_title": "..."
  }
}
```

**To jest POPRAWNA sciezka.** Standardowy WP REST `meta` field **cicho ignoruje** `rank_math_*` keys — kod w `injector.py` ma komentarz: "WP REST 'meta' field silently ignores RankMath keys — use update_rankmath_meta() separately".

---

### Format multi-keyword dla RankMath

**Format:** `"fraza1,fraza2,fraza3"` — comma-separated string (NIE JSON array)

| Aspekt | Wartosc |
|--------|---------|
| Pole API | `rank_math_focus_keyword` |
| Format multi | `"fraza1,fraza2,fraza3"` |
| Separator | przecinek bez spacji |
| Pierwsza fraza | traktowana jako Primary Focus Keyword |
| Limit fraz | brak hard limitu; praktycznie 2-5 fraz |
| Endpoint | `rankmath/v1/updateMeta` (rekomendowany) |

---

### Aktualne pole w generatorze — diagnoza

**Pole w generatorze:** `focus_keyphrase` (singular) — jeden string

**Przeplyw danych:**
```
core/generator.py -> generate_seo_v4()
  LLM zwraca JSON z polem: "focus_keyphrase": "..."

core/injector.py -> _build_rankmath_meta(seo)
  focus_keyword = seo.get("focus_keyphrase", "").strip()
  meta["rank_math_focus_keyword"] = focus_keyword  # jeden string
```

**GAP: brak multi-keyword support**

| Co jest | Co powinno byc |
|---------|----------------|
| Generator: `focus_keyphrase` = "fraza glowna" | `focus_keyphrases` = ["fraza1", "fraza2", "fraza3"] |
| Injector: wysyla jeden string | Injector: laczy liste przecinkami -> "fraza1,fraza2" |
| Brak SAAS keywords w meta | SAAS priority_keywords moglby uzupelniac focus_keyphrases |

---

### SAAS enrichment a focus_keyword

**Odkrycie:** SAAS `priority_keywords` (z GSC) sa wstrzykiwane tylko do PROMPTU generatora. NIE sa wysylane do RankMath meta.

Obecny przeplyw:
```
SAAS priority_keywords -> prompt LLM (jako dodatkowy kontekst)
                       -> NIE trafia do rank_math_focus_keyword
```

Potencjal: pierwsze 2-3 `priority_keywords` moglby byc dolaczone do `rank_math_focus_keyword` jako multi-keyword string.

---

## Rekomendacje dla Supervisora

### Lista actionable items (priorytet malejacy)

**R1. Weryfikacja duplikatu VideoObject — PILNE**
Sprawdzic https://search.google.com/test/rich-results dla losowego posta z VSE.
Jesli RankMath generuje swoj VideoObject -> wylaczyc w ustawieniach RankMath (Auto-detect Video).
*Dispatch do: vse-dev (konfiguracja) lub manualnie przez admina WP*

**R2. Multi-keyword support — generator + injector**
Zmieniac generator: LLM powinien zwracac `focus_keyphrases: ["fraza1", "fraza2"]` (lista 2-4 fraz).
Zmieniac injector `_build_rankmath_meta()`: zlaczyc liste -> `",".join(focus_keyphrases)` -> wyslac do RankMath.
*Dispatch do: vse-dev*

**R3. Usunac Quotation schema z nowych generacji**
Usunac petle Quotation w `core/injector.py` > `build_schema_jsonld()`.
Istniejace posty z Quotation — zostawic (nie re-injektowac).
*Dispatch do: vse-dev — 10 linii kodu, niskokosztowe*

**R4. SAAS keywords -> RankMath focus_keyword**
Po R2: opcjonalnie dolaczyc SAAS `priority_keywords[0:2]` do multi-keyword stringa.
Priorytet: niski (R2 musi byc najpierw).
*Dispatch do: vse-dev*

**R5. interactionStatistic coverage**
Sprawdzic czy `YT_API_KEY` jest dostepny w env na VPS.
Jesli nie — wdrozyc fallback lub zaakceptowac brak tego pola.
*Dispatch do: vse-runner lub manualnie*

---

## Podsumowanie techniczne

| Obszar | Status | Ocena |
|--------|--------|-------|
| Schema w raw content | OK | Google crawluje z body |
| VideoObject kompletnosc | OK | wszystkie wymagane pola |
| uploadDate z TZ | OK | timezone append zaimplementowany |
| Clip (hasPart) | OK | anchor-matched chapters |
| Quotation schema | ZBEDNA | do usuniecia z nowych generacji |
| Duplikat VideoObject (RankMath) | DO WERYFIKACJI | ryzyko wysokie |
| RankMath endpoint | OK | `rankmath/v1/updateMeta` |
| focus_keyword format | OK kanal | brak multi-keyword |
| Generator: focus_keyphrases | GAP | tylko singular, brak listy |
| SAAS keywords -> RankMath | GAP | keywords tylko w prompcie, nie w meta |

---

*vse-analyst-03 | video-seo-engine | 2026-06-19 22:18*
