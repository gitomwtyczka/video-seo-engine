# DISPATCH VSE-ANALYST — A1+A2: Schema.org & RankMath Audit
**Data:** 2026-06-19 | **Supervisor:** 01 | **Priorytet:** Analiza przed implementacja

---

## 🔴 WAZNA ZMIANA OPERACYJNA

`run_command` jest ZABLOKOWANY na Windows sandbox permanentnie.

**NIE uruchamiaj** zadnych komend shellowych (python, curl, git, itp.).

**Twoje zadanie:** TYLKO czytaj pliki i pisz raport:
- Odczyt: `mcp_github_get_file_contents`
- Zapis raportu: `mcp_github_create_or_update_file`
- PAMIETAJ o SHA przy aktualizacji istniejacego pliku!

Jesli potrzebujesz komendy shellowej (np. curl do RankMath docs) —
PRZECZYTAJ dokumentacje przez `read_url_content` lub `search_web`.

---

## TWOJ CALLSIGN
Uzyj: `vse-analyst-03`

## KONTEKST
VSE publikuje artykuly wideo na WordPress. Generuje schema.org JSON-LD i ustawia meta SEO.
Potrzebujemy audytu — czy schema i keywords trafiaja prawidlowo do RankMath.

**Repo:** `gitomwtyczka/video-seo-engine` branch `main`

---

## ZADANIE A1 — Schema.org Audit

### Pytania do odpowiedzi

1. **Gdzie trafia schema.org?**
   - Przeczytaj `inject_rest_v5.py` via GitHub MCP
   - Czy schema JSON-LD jest wstrzykiwana jako `<!-- wp:html --><script type="application/ld+json">` w content?
   - Czy jest tez ustawiana przez `yoast_head_json` lub RankMath REST field?

2. **Czy VideoObject schema jest kompletna?**
   - Sprawdz czy zawiera: `name`, `description`, `thumbnailUrl`, `uploadDate`, `contentUrl`, `embedUrl`, `duration`, `hasPart` (Clip)
   - Google wymaga: `name`, `description`, `thumbnailUrl`, `uploadDate` — czy wszystkie sa zawsze wypelnione?

3. **Quotation schema — status**
   - Google oficjalnie nie renderuje Quotation w rich results
   - Rekomendacja: zostawic czy usunac?
   - Jesli usunac — opisz gdzie w kodzie jest generowana

4. **RankMath REST API — jak ustawiane sa meta SEO?**
   - Przeczytaj `core/injector.py` via GitHub MCP
   - Czy jest tam ustawianie `rankmath_title`, `rankmath_description`, `rankmath_focus_keyword`?
   - Format dla wielu fraz: `"fraza1,fraza2"` czy tablica?
   - Mozesz sprawdzic dokumentacje: `read_url_content` na https://rankmath.com/kb/rest-api/

### Zrodla do sprawdzenia
- `core/injector.py` (GitHub MCP)
- `inject_rest_v5.py` (GitHub MCP)

---

## ZADANIE A2 — Multiple Focus Keywords

### Pytania do odpowiedzi

1. Jak RankMath v1 REST API przyjmuje wiele focus keywords?
   - Pole: `rankmath_focus_keyword`
   - Format: `"fraza1,fraza2,fraza3"` (przecinki) czy JSON array?
   - Limit: ile fraz maksymalnie?

2. Czy generator.py produkuje pole `focus_keyphrase` (singular) czy `focus_keyphrases` (plural)?
   - Sprawdz `core/generator.py` — co zwraca LLM i co trafia do REST API

3. Czy pole z generatora jest faktycznie wysylane do RankMath w injector?

---

## OUTPUT — Format raportu

Napisz raport z sekcjami:

```markdown
## A1: Schema.org
- Gdzie trafia: [content raw / RankMath meta / oba]
- VideoObject kompletnosc: [OK / brakuje: X, Y]
- Quotation schema: [rekomendacja: zostaw/usun]

## A2: RankMath API
- Format focus_keyword: [format]
- Limit fraz: [N]
- Aktualne pole w generatorze: [focus_keyphrase/focus_keyphrases]
- Gap: [co trzeba zmienic]

## Rekomendacje dla Supervisora
[lista actionable items dla D5 dispatcha]
```

---

## DOSTEP
```
GitHub MCP:
  owner: gitomwtyczka, repo: video-seo-engine, branch: main
Pliki: core/injector.py, core/generator.py, inject_rest_v5.py
```

**Workflow przy edycji pliku raportu:**
1. Jesli raport jeszcze nie istnieje — `create_or_update_file` bez `sha` (nowy plik)
2. Jesli aktualizujesz — pobierz `sha` najpierw przez `get_file_contents`

## HEARTBEAT I RAPORT
- Heartbeat: `.agents/heartbeat.json` w `video-seo-engine` main
- Raport: `.agents/reports/2026-06-19_vse-analyst-03_schema-rankmath-audit.md`
- Dual-write inbox: `sonic-void master .agents/reports/inbox/2026-06-19_vse-analyst-03_schema-rankmath-audit.md`

*Supervisor 01 | video-seo-engine | 2026-06-19*
