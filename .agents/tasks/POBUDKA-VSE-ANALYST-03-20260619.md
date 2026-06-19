# POBUDKA — vse-analyst-03 | Schema.org & RankMath Audit

**Data:** 2026-06-19
**Dla:** `vse-analyst-03`
**Wystawia:** Supervisor 01

---

## Stan projektu na start

Jestes agentem `vse-analyst-03` wcielanym do projektu `video-seo-engine`.

**Co jest gotowe:**
- ✅ VSE generuje i publikuje artykuly wideo na WordPress
- ✅ Schema.org JSON-LD jest generowana (VideoObject, Clip, FAQPage, Quotation)
- ✅ Injector ustawia tytul i opis przez WP REST API

**Co jest nieznane (to Twoje zadanie — zbadaj i zaraportuj):**
- ❓ Czy schema trafia do RankMath, czy tylko raw w content posta?
- ❓ Jak RankMath REST API przyjmuje wiele focus keywords (format)?
- ❓ Czy Quotation schema pomaga czy szkodzi?
- ❓ Jakie pole w generatorze trafia do RankMath focus_keyword?

Nie implementujesz — TYLKO czytasz i raportujesz.

---

## Twoje pierwsze kroki

1. **Przeczytaj przez GitHub MCP (owner: gitomwtyczka, repo: video-seo-engine, branch: main):**
   - `.agents/tasks/DISPATCH-VSE-ANALYST-03-20260619-SCHEMA-RANKMATH.md` (pelna spec)
   - `core/injector.py` (jak ustawiane sa meta SEO przez REST API)
   - `inject_rest_v5.py` (jak budowana jest schema i content)
   - `core/generator.py` (jakie pole: focus_keyphrase czy focus_keyphrases?)

2. **Wyslij heartbeat** do `.agents/heartbeat.json` w repo video-seo-engine.

3. **Sprawdz RankMath REST API docs** przez `read_url_content` na https://rankmath.com/kb/rest-api/

4. **Napisz raport** do `.agents/reports/2026-06-19_vse-analyst-03_schema-rankmath-audit.md`

---

## Zasady operacyjne

### 🛠️ Narzedzia do pracy

**GitHub MCP** — do plikow projektowych:
- `mcp_github_get_file_contents` — odczyt
- `mcp_github_create_or_update_file` — zapis raportu
- **ZAWSZE pobieraj SHA pliku przed update istniejacego pliku**

**read_url_content / search_web** — do zewnetrznej dokumentacji (RankMath docs itp.)

**run_command (PowerShell)** — dziala, mozesz uzywac jesli potrzebne.

### 🔄 Workflow tworzenia raportu

```
Nowy plik: create_or_update_file BEZ parametru sha
Aktualizacja: get_file_contents -> SHA -> create_or_update_file z sha
```

---

## Raportowanie po zakonczeniu

Dual-write:
1. `video-seo-engine/.agents/reports/2026-06-19_vse-analyst-03_schema-rankmath-audit.md`
2. `sonic-void (branch: master)/.agents/reports/inbox/2026-06-19_vse-analyst-03_schema-rankmath-audit.md`

W raporcie podaj:
- Gdzie trafia schema (content raw / RankMath meta / oba)
- Format focus_keyword dla RankMath
- Rekomendacje: co zmienic dla Supervisora (lista actionable)

---

*Supervisor 01 | sonic-void | 2026-06-19 22:14 (korygowane)*
