# DISPATCH VSE-ANALYST — A1+A2: Schema.org & RankMath Audit
**Data:** 2026-06-19 | **Supervisor:** 01 | **Priorytet:** 🟡 Analiza przed implementacją

---

## TWÓJ CALLSIGN
Użyj: `vse-analyst-03`

## KONTEKST
VSE publikuje artykuły wideo na WordPress. Generuje schema.org JSON-LD i ustawia meta SEO.
Potrzebujemy audytu — czy schema i keywords trafiają prawidłowo do RankMath.

**Repo:** `gitomwtyczka/video-seo-engine` branch `main`

---

## ZADANIE A1 — Schema.org Audit

### Pytania do odpowiedzi

1. **Gdzie trafia schema.org?**
   - Przeczytaj `inject_rest_v5.py` → `build_schema_jsonld()` i `build_post_content()`
   - Czy schema JSON-LD jest wstrzykiwana jako `<!-- wp:html --><script type="application/ld+json">` w content?
   - Czy jest też ustawiana przez `yoast_head_json` lub RankMath REST field?

2. **Czy VideoObject schema jest kompletna?**
   - Sprawdź czy zawiera: `name`, `description`, `thumbnailUrl`, `uploadDate`, `contentUrl`, `embedUrl`, `duration`, `hasPart` (Clip)
   - Google wymaga: `name`, `description`, `thumbnailUrl`, `uploadDate` — czy wszystkie są zawsze wypełnione?

3. **Quotation schema — status**
   - Google oficjalnie nie renderuje Quotation w rich results
   - Ale czy jej obecność szkodzi? Sprawdź via Google Rich Results Test guidelines
   - Rekomendacja: zostawić czy usunąć?

4. **RankMath REST API — jak ustawiane są meta SEO?**
   - Przeczytaj `core/injector.py` — czy jest tam ustawianie `rankmath_title`, `rankmath_description`, `rankmath_focus_keyword`?
   - Jakie pola REST API WP obsługuje RankMath dla: focus keyword, seo title, meta description?
   - Format dla wielu fraz: `"fraza1,fraza2"` czy tablica?

### Źródła do sprawdzenia
- `core/injector.py` (GitHub MCP)
- `inject_rest_v5.py` (GitHub MCP)
- Dokumentacja RankMath REST API: https://rankmath.com/kb/rest-api/

---

## ZADANIE A2 — Multiple Focus Keywords

### Pytania do odpowiedzi

1. Jak RankMath v1 REST API przyjmuje wiele focus keywords?
   - Pole: `rankmath_focus_keyword`
   - Format: `"fraza1,fraza2,fraza3"` (przecinki) czy JSON array?
   - Limit: ile fraz maksymalnie?

2. Sprawdź czy w screenie z RankMath (opisanym przez usera) widać:
   - Ile aktualnie jest focus keywords?
   - Jakie błędy dokładnie zgłasza RankMath (lista po prawej stronie)

3. Czy generator.py produkuje pole `focus_keyphrase` (singular) czy `focus_keyphrases` (plural)?
   - Sprawdź `core/generator.py` — co zwraca LLM i co trafia do REST API

---

## OUTPUT — Format raportu

Napisz raport `.agents/reports/2026-06-19_vse-analyst-03_schema-rankmath-audit.md` z sekcjami:

```markdown
## A1: Schema.org
- Gdzie trafia: [content raw / RankMath meta / oba]
- VideoObject kompletność: [OK / brakuje: X, Y]
- Quotation schema: [rekomendacja: zostaw/usuń]

## A2: RankMath API
- Format focus_keyword: [format]
- Limit fraz: [N]
- Aktualne pole w generatorze: [focus_keyphrase/focus_keyphrases]
- Gap: [co trzeba zmienić]

## Rekomendacje dla Supervisora
[lista actionable items dla D5 dispatcha]
```

## DOSTĘP
```
GitHub MCP:
  owner: gitomwtyczka, repo: video-seo-engine, branch: main
Pliki: core/injector.py, core/generator.py, inject_rest_v5.py
```

## HEARTBEAT I RAPORT
- Heartbeat: `.agents/heartbeat.json` w `video-seo-engine` main
- Raport: `.agents/reports/2026-06-19_vse-analyst-03_schema-rankmath-audit.md`
- Dual-write inbox: `sonic-void master .agents/reports/inbox/2026-06-19_vse-analyst-03_schema-rankmath-audit.md`

*Supervisor 01 | video-seo-engine | 2026-06-19*
