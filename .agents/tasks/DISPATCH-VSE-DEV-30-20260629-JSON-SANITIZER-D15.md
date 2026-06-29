## ⚡ KROK 0 — ZANIM cokolwiek zrobisz

**0. Wczytaj blok systemowy:**
view_file → C:\Users\tomas2\.gemini\antigravity\playground\sonic-void\.agents\protocols\dispatch-system-block.md

---

# DISPATCH D15 — JSON Pre-parse Sanitizer

**Callsign:** vse-dev-30  
**Projekt:** video-seo-engine  
**Data:** 2026-06-29  
**Priorytet:** 🔴 KRYTYCZNY — blokuje 80+ RankMath

---

## Twój deliverable

Działający commit na VPS + raport do Supervisora. Dodajesz dwie funkcje do `core/generator.py` i modyfikujesz wywołanie `json.loads()` w `generate_seo_v4()`. **Czas szacowany: 15-20 min.**

---

## Kontekst (przeczytaj PRZED kodowaniem)

Analiza A11 (vse-analyst-10, 2026-06-21) udokumentowała root cause:

**Root cause:** LLM (głównie Claude) generuje HTML wewnątrz JSON string z nieescapowanymi cudzysłowami w atrybutach HTML:
```
{"article_body": "<a href=\"https://example.com\" target=\"_blank\">tekst</a>"}
```
To powoduje `JSONDecodeError` w `json.loads()` w `core/generator.py`.

D12 (retry + prompt) był łatką symptomów. D15 = deterministyczna warstwa kodu PRZED `json.loads()`.

---

## Plik do edycji

`core/generator.py` w repo `video-seo-engine` (branch: `main`)

Pobierz:
```
mcp_github_get_file_contents:
  owner: gitomwtyczka  repo: video-seo-engine  path: core/generator.py
```

---

## Co dodać — dokładna specyfikacja

### Krok 1: Dodaj dwie nowe funkcje (PRZED `generate_seo_v4`)

```python
def _sanitize_llm_json(raw_text: str) -> str:
    """Fix common LLM JSON errors before parsing.
    
    Root cause (D15/A11): LLM generates HTML attributes with unescaped double
    quotes inside JSON string values, breaking json.loads().
    Fix: Replace escaped-quote HTML attributes with single-quote equivalents
    BEFORE parsing.
    """
    result = re.sub(
        r'(\w+)=\\"([^\\]*?)\\"',
        lambda m: f"{m.group(1)}='{m.group(2)}'",
        raw_text
    )
    return result


def _post_parse_html_cleanup(seo_data: dict) -> dict:
    """After successful json.loads(), ensure HTML attributes use single quotes.
    
    Defense-in-depth layer 4: catches remaining double quotes in HTML
    that survived the pre-parse sanitizer.
    """
    for field in ['article_body', 'lead']:
        html = seo_data.get(field, '')
        if html and '"' in html:
            cleaned = re.sub(
                r'(<[^>]*?)(\w+)="([^"]*)"([^>]*?>)',
                lambda m: f"{m.group(1)}{m.group(2)}='{m.group(3)}'{m.group(4)}",
                html
            )
            seo_data[field] = cleaned
    return seo_data
```

### Krok 2: Zmodyfikuj `generate_seo_v4()` — w miejscu `json.loads(text)`

Znajdź:
```python
        text = _call_llm(prompt, api_key, provider)
        text = text.strip()
        text = re.sub(r"^```json\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        return json.loads(text)
```

Zmień na:
```python
        text = _call_llm(prompt, api_key, provider)
        text = text.strip()
        text = re.sub(r"^```json\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = _sanitize_llm_json(text)           # D15: Warstwa 2 — pre-parse sanitizer
        result = json.loads(text)
        result = _post_parse_html_cleanup(result)  # D15: Warstwa 4 — post-parse cleanup
        return result
```

**UWAGA:** Jeśli D12 dodał blok retry (drugi `json.loads()`), zastosuj ten sam pattern tam również.

---

## Deploy

Po commicie przez GitHub MCP:
```bash
ssh root@147.224.162.100 "cd /home/ubuntu/video-seo-engine && git pull origin main && docker compose up -d --build vse-api"
```

Sprawdź logi:
```bash
ssh root@147.224.162.100 "docker logs vse-api --tail 100 2>&1 | tail -50"
```

---

## Raport końcowy

1. Raport: `.agents/reports/2026-06-29_vse-dev-30_json-sanitizer-d15.md`
2. Dual-write: `sonic-void/.agents/reports/inbox/`
3. Heartbeat `status: done` z commit SHA w `last_completed`

---

*[Supervisor 01 | sonic-void 29.06.2026]*