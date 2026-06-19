# DISPATCH VSE-DEV — D1+D2+D3: Publication Quality Fix
**Data:** 2026-06-19 | **Supervisor:** 01 | **Priorytet:** KRYTYCZNY + WYSOKI

---

## 🔴 WAZNA ZMIANA OPERACYJNA

`run_command` jest ZABLOKOWANY na Windows sandbox permanentnie.

**NIE uruchamiaj:** python, pytest, ruff, pip, git, npm ani zadnych komend shellowych.

**Twoje zadanie:** TYLKO edytuj pliki przez:
- `mcp_github_get_file_contents` — odczyt plikow z repo
- `mcp_github_create_or_update_file` — zapis/aktualizacja plikow
- PAMIETAJ o pobieraniu SHA przed kazdym update istniejacego pliku!

Weryfikacja (testy, uruchomienie) bedzie zrobiona OSOBNO przez Supervisora po twoich zmianach.

Jesli potrzebujesz komendy shellowej — STOP — zaraportuj do Supervisora.

---

## ⚠️ ZASADY DLA SSH I ZAGNIEZDZONE CUDZYSŁOWY

Jesli musisz wydac komende przez SSH do VPS (np. git pull, docker restart) — nie robi tego worker sam.
**Raportuj do Supervisora** z gotową komendą — Supervisor wykona przez run_command.

Dla Supervisora: przy SSH z PowerShell uwazaj na zagniezdzone cudzyslowy.
Bezpieczny wzorzec:
```powershell
# Prosta komenda:
ssh root@147.224.162.100 "git pull origin main"

# Komenda ze zmiennymi (uzyj here-string lub skryptu na VPS):
$cmd = 'cd /opt/vse && git pull origin main && docker compose restart api'
ssh root@147.224.162.100 $cmd

# Jesli komenda zawiera cudzyslowy wewnetrzne — uzywaj apostrofow w bashu:
ssh root@147.224.162.100 'bash -c "echo hello"'
```

NIGDY nie zagniezdzaj `"` w `"` bez escape. Testuj najpierw prosta komenda `echo ok`.

---

## TWOJ CALLSIGN
Uzyj: `vse-dev-17`

## KONTEKST
VSE generuje artykuly wideo i publikuje je przez WordPress REST API.
Sa 3 powiazane problemy z jakoscia publikacji — naprawiasz je w tej sesji.

**Repo:** `gitomwtyczka/video-seo-engine` branch `main`

---

## ZADANIE D1 — Bug: Hardcoded branding w SEO title

### Problem
W `core/generator.py` prompt ma hardcoded `"| Prawy TV"` w instrukcji generowania `seo_title`.
Gdy artykul idzie na inny portal (kurier365), branding jest zawsze Prawy TV.

**Linia promptu (do zmiany):**
```
3. **seo_title** — max 60 znakow, dla tagu <title> i RankMath. Z branding pipe: "| Prawy TV".
```

### Fix
1. Pobierz i przeczytaj `core/generator.py` i `core/profile.py` przez GitHub MCP
2. Sprawdz strukture plikow profilu w katalogu `profiles/`
3. Dodaj pole `site_brand` do profilu portalu (np. `"site_brand": "Prawy TV"`)
4. W `generate_seo_v4()` dodaj parametr `site_brand: Optional[str] = None`
5. W `process_video()` przekaz `site_brand` dalej
6. W prompcie zamien hardcode: zamiast `"| Prawy TV"` uzywaj dynamicznego `site_brand`
   albo pomijaj branding jesli None

### Weryfikacja (bez uruchamiania kodu)
- Grep po slowie "Prawy TV" w generator.py — nie powinno byc jako literal w stringu promptu
- Sygnatura funkcji zawiera `site_brand: Optional[str] = None`

---

## ZADANIE D2+D3 — Restrukturyzacja artykulu + cytaty w podsumowaniu

### Problem
Obecna kolejnosc sekcji w `build_post_content()`:
```
lead --> YT embed --> Rozdzialy nagrania --> article_body --> Kluczowe cytaty --> FAQ
```

Pozadana kolejnosc:
```
lead --> [PIERWSZY AKAPIT z article_body] --> YT embed --> Rozdzialy nagrania --> [RESZTA article_body] --> Podsumowanie (cytaty) --> FAQ
```

### Fix

**Krok 1: Dodaj helper do wyodrebnienia pierwszego akapitu**
```python
import re

def _split_first_paragraph(html: str) -> tuple[str, str]:
    """Zwraca (pierwszy_p, reszta_html)."""
    match = re.search(r'(<p>.*?</p>)', html, re.DOTALL)
    if match:
        first_p = match.group(1)
        rest = html[match.end():].strip()
        return first_p, rest
    return "", html
```

**Krok 2: W build_post_content() uzyj helpera**
```python
first_p, rest_body = _split_first_paragraph(article_body)

intro_block = """<!-- wp:html -->\n""" + first_p + """\n<!-- /wp:html -->""" if first_p else ""
body_rest_block = """<!-- wp:html -->\n""" + rest_body + """\n<!-- /wp:html -->""" if rest_body else ""
```

**Krok 3: Zmien heading cytatow**
```python
# Zamiast: <h2>Kluczowe cytaty</h2>
# Daj:     <h2>Podsumowanie</h2>
```

**Krok 4: Nowa kolejnosc w return**
```python
return (
    f"{lead_block}\n\n"
    f"{intro_block}\n\n"
    f"{embed_block}\n\n"
    f"{chapters_block}\n\n"
    f"{body_rest_block}\n\n"
    f"{quotes_section}\n\n"
    f"{faq_section}\n\n"
    f"{schema_block}\n\n"
    f"{js_block}"
)
```

**WAZNE:** `inject_rest_v5.py` to STARY standalone script.
Sprawdz czy nowy pipeline uzywa `core/injector.py`. Jesli tak — zastosuj te same zmiany
w `core/injector.py`. Przeczytaj oba pliki i zdecyduj gdzie jest aktywny kod.

### Weryfikacja (bez uruchamiania kodu)
- W kodzie `build_post_content`: `intro_block` wystepuje PRZED `embed_block`
- Heading cytatow to string "Podsumowanie" nie "Kluczowe cytaty"

---

## DOSTEP DO REPO
```
GitHub MCP:
  owner: gitomwtyczka
  repo: video-seo-engine
  branch: main

Kluczowe pliki:
  core/generator.py
  core/injector.py
  core/profile.py
  inject_rest_v5.py
  profiles/ (sprawdz co jest)
```

**Workflow przy edycji pliku:**
1. `get_file_contents` — pobierz plik + zanotuj pole `sha`
2. Przygotuj nowa zawartosc
3. `create_or_update_file` z parametrem `sha` (bez SHA — blad!)

## HEARTBEAT I RAPORT
- Heartbeat start: `.agents/heartbeat.json` w `video-seo-engine` main
- Raport: `.agents/reports/2026-06-19_vse-dev-17_publication-quality-d1d2d3.md`
- Dual-write inbox: `sonic-void master .agents/reports/inbox/2026-06-19_vse-dev-17_publication-quality-d1d2d3.md`

## COMMIT MSG FORMAT
```
fix: remove hardcoded Prawy TV branding, add site_brand param [vse-dev-17]
feat: restructure article layout, first para before embed [vse-dev-17]
feat: quotes section renamed to Podsumowanie [vse-dev-17]
```

*Supervisor 01 | video-seo-engine | 2026-06-19*
