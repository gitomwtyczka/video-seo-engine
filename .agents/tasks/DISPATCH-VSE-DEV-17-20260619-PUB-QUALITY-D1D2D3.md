# DISPATCH VSE-DEV — D1+D2+D3: Publication Quality Fix
**Data:** 2026-06-19 | **Supervisor:** 01 | **Priorytet:** KRYTYCZNY + WYSOKI

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
1. Przeczytaj `core/generator.py` i `core/profile.py`
2. Sprawdz strukture pliku profilu w katalogu `profiles/`
3. Dodaj pole `site_brand` do profilu portalu
4. W `generate_seo_v4()` dodaj parametr `site_brand: Optional[str] = None`
5. W `process_video()` przekaz `site_brand` dalej
6. W prompcie zamien hardcode: zamiast `"| Prawy TV"` uzywaj dynamicznego `site_brand` albo pomijaj branding jesli None

### Weryfikacja
- Prompt nie zawiera slowa "Prawy TV" jako literal
- Funkcja akceptuje `site_brand=None` i `site_brand="Kurier365"` bez bledu

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

intro_block = """<!-- wp:html -->\n{first_p}\n<!-- /wp:html -->""".format(first_p=first_p) if first_p else ""
body_rest_block = """<!-- wp:html -->\n{rest_body}\n<!-- /wp:html -->""".format(rest_body=rest_body) if rest_body else ""
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

### Weryfikacja
- HTML zawiera `<p>` z article_body PRZED `<!-- wp:embed -->`
- Sekcja cytatow ma heading "Podsumowanie" nie "Kluczowe cytaty"

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
