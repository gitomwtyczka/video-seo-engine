# POBUDKA — vse-dev-17 | Publication Quality Fix

**Data:** 2026-06-19
**Dla:** `vse-dev-17`
**Wystawia:** Supervisor 01

---

## Stan projektu na start

Jestes agentem `vse-dev-17` wcielanym do projektu `video-seo-engine`.

**Co jest gotowe (nie rob tego ponownie):**
- ✅ VSE generuje artykuly wideo i publikuje na WordPress przez REST API
- ✅ Pipeline: VTT -> LLM (Gemini/Claude) -> injector -> WP
- ✅ Schema.org JSON-LD (VideoObject + Clip + Quotation) dziala
- ✅ Rozdzialy wideo z seekTo (JavaScript player) dziala

**Co jest problemem (to Twoje zadanie):**
- ❌ SEO title ma hardcoded branding `"| Prawy TV"` w prompcie generatora
- ❌ Kolejnosc sekcji w artykule suboptymalna (embed YT przed pierwszym akapitem)
- ❌ Sekcja cytatow wymaga rebrandingu na "Podsumowanie"

---

## Twoje pierwsze kroki

1. **Przeczytaj przez GitHub MCP (owner: gitomwtyczka, repo: video-seo-engine, branch: main):**
   - `.agents/tasks/DISPATCH-VSE-DEV-17-20260619-PUB-QUALITY-D1D2D3.md` (pelna spec zadania)
   - `core/generator.py` (prompt z hardcoded brandem)
   - `core/injector.py` (build_post_content — aktywny kod pipeline)
   - `inject_rest_v5.py` (stary standalone — sprawdz czy pipeline go uzywa)

2. **Wyslij heartbeat** do `.agents/heartbeat.json` w repo video-seo-engine.

3. **Implementuj** w kolejnosci z dispatchu: D1 (branding) -> D2+D3 (struktura).

---

## Zasady operacyjne

### 🛠️ Narzedzia do pracy

**GitHub MCP** — do plikow projektowych (jedyne zrodlo prawdy):
- `mcp_github_get_file_contents` — odczyt
- `mcp_github_create_or_update_file` — zapis
- **ZAWSZE pobieraj SHA pliku przed update** (inaczej blad 409 Conflict)

**run_command (PowerShell)** — dziala, mozesz uzywac do operacji lokalnych.

**SSH do VPS** (jesli potrzebne):
```powershell
ssh root@147.224.162.100 "komenda"
# Uwaga na zagniezdzone cudzyslowy!
# Bezpieczny wzorzec dla zlozonych komend:
$cmd = 'cd /opt/vse && docker compose restart api'
ssh root@147.224.162.100 $cmd
# Cudzyslowy wewnetrzne — apostrofy w bashu:
ssh root@147.224.162.100 'bash -c "echo hello"'
```

### 🔄 Workflow edycji pliku w repo

```
1. get_file_contents -> zanotuj pole "sha"
2. Przygotuj nowa zawartosc
3. create_or_update_file z sha=<zanotowany SHA>
```

### 🔧 Ktory plik edytowac?

`inject_rest_v5.py` to STARY standalone script.
Jesli `core/injector.py` zawiera `build_post_content()` — edytuj ten.
Jesli nie — edytuj `inject_rest_v5.py`.
Przeczytaj oba i zdecyduj.

---

## Raportowanie po zakonczeniu

Dual-write:
1. `video-seo-engine/.agents/reports/2026-06-19_vse-dev-17_publication-quality-d1d2d3.md`
2. `sonic-void (branch: master)/.agents/reports/inbox/2026-06-19_vse-dev-17_publication-quality-d1d2d3.md`

W raporcie podaj:
- SHA commitow (po jednym per zadanie)
- Ktory plik byl aktywny (injector.py czy inject_rest_v5.py)
- Czy prompt generator.py nie zawiera juz slowa "Prawy TV" jako literal

---

*Supervisor 01 | sonic-void | 2026-06-19 22:14 (korygowane)*
