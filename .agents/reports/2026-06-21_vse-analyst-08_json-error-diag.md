# A8: Diagnostyka JSON Error — Raport

**Callsign:** vse-analyst-08  
**Data:** 2026-06-21  
**Dispatch:** DISPATCH-VSE-ANALYST-08-20260621-JSON-ERROR-DIAG  
**Status:** raport kompletny

---

## Traceback

```
2026-06-21 09:36:57,618 [INFO] httpx: HTTP Request: POST https://api.anthropic.com/v1/messages "HTTP/1.1 200 OK"
2026-06-21 09:36:57,643 [ERROR] core.generator: claude call failed: Expecting ',' delimiter: line 13 column 330 (char 1257)
2026-06-21 09:36:57,644 [ERROR] api.routers.generate: [/v1/generate] ValueError: Expecting ',' delimiter: line 13 column 330 (char 1257)
INFO:     172.27.0.1:41532 - "POST /v1/generate HTTP/1.0" 422 Unprocessable Entity
```

**Kontekst wywołania:**
```
2026-06-21 09:35:35,525 [INFO] api.routers.generate: [/v1/generate] video_url=https://www.youtube.com/watch?v=vWaaDIXMb1M provider=claude type=watching_page profile=kurier365
2026-06-21 09:35:52,697 [INFO] core.generator: Calling claude for: KIJÓW ODPOWIADA NAWROCKIEMU. RZĄD KRYTYKUJE ODEBRANIE ORDERU [type=watching_page]
```

## Przyczyna

**Claude (claude-sonnet-4-5) zwrócił HTTP 200 OK z treścią która NIE jest poprawnym JSONem.**

Dokładna ścieżka błędu:

1. `api/routers/generate.py`: `result = await run_generate(...)` → wywołuje pipeline
2. `api/services/pipeline.py`: `seo = await asyncio.to_thread(generate_schema, ...)` → wywołuje generator
3. `core/generator.py` → `generate_seo_v4()`:
   - `text = _call_llm(prompt, api_key, "claude")` — Anthropic API odpowiada 200 OK
   - `text = text.strip()` — OK
   - `text = re.sub(r"^```json\s*", "", text)` — strip markdown code fence
   - `text = re.sub(r"\s*```$", "", text)` — strip closing fence
   - **`json.loads(text)` → FAIL: `json.JSONDecodeError: Expecting ',' delimiter: line 13 column 330 (char 1257)`**
4. `except Exception as exc: logger.error(...); raise` — re-raise
5. `api/routers/generate.py`: `except ValueError as exc: raise HTTPException(422, detail=str(exc))`
6. Frontend: `if (!res.ok) { detail = data.detail; throw new Error(detail) }` → user widzi błąd

**Typ błędu: `json.JSONDecodeError` (podklasa `ValueError`)** — parsowanie char 1257, linia 13, kolumna 330.

Pozycja char 1257 sugeruje że błąd jest w środku **`article_body`** (pole HTML ~1000-1500 znaków).
Najprawdopodobniej Claude wstawił niezescapowany cudzysłów podwójny wewnątrz wartości JSON string
(np. w atrybucie HTML `target="_blank"` wewnątrz `article_body` — podwójne cudzysłowy nie zostały
escape'owane jako `\"`).

## Dowody

### 1. Logi VPS — potwierdzone

| Timestamp (UTC) | Log | Opis |
|---|---|---|
| 09:35:35.525 | `[/v1/generate] video_url=...vWaaDIXMb1M provider=claude type=watching_page profile=kurier365` | Request zarejestrowany |
| 09:35:40.642 | `D11 thumbnails: 1 downloaded` | Thumbnail pobrany |
| 09:35:40.642 | `D11 image[0]: SAAS Vision unavailable — LLM fallback pending` | SAAS niedostępny |
| 09:35:40.643 | `LOCAL_RUNNER_MODE=true — delegating transcript` | Transkrypt przez Local Runner |
| 09:35:52.679 | `__VTT__ format detected — converting to WebVTT` | VTT conversion OK |
| 09:35:52.697 | `Calling claude for: KIJÓW ODPOWIADA NAWROCKIEMU...` | Claude wywołany |
| 09:36:57.618 | `HTTP Request: POST api.anthropic.com "HTTP/1.1 200 OK"` | **Claude odpowiedział 200** |
| 09:36:57.643 | `[ERROR] claude call failed: Expecting ',' delimiter` | **`json.loads()` FAIL** |
| 09:36:57.644 | `[ERROR] [/v1/generate] ValueError: Expecting ',' delimiter` | Router → 422 |

### 2. Kontener status

- `vse-api`: Up 5 hours (restart o ~09:21 UTC — PRZED błędem)
- `vse-web`: Up 16 hours
- `vse-postgres`: Up 3 days (healthy)

### 3. Jednorazowy błąd

W ciągu 5h od restartu kontenera, zarejestrowano **dokładnie 1 wywołanie `/v1/generate`** i **dokładnie 1 błąd**.
Brak wcześniejszych sukcesów tego dnia dla porównania.

### 4. Frontend error handling

`web/src/app/dashboard/dashboard-inner.tsx`:
```typescript
// linia 832:
try { data = await res.json() } catch { ... }
// linia 837-838:
const detail = (data as ...)?.detail
throw new Error(typeof detail === 'string' ? detail : `Błąd serwera: HTTP ${res.status}`)
```
Frontend poprawnie wyciąga `detail` string z 422 response i wyświetla go userowi.

### 5. Brak surowego LLM output w logach

**KRYTYCZNY BRAK**: `generator.py` NIE loguje surowego output Claude'a przed `json.loads()`.
Nie da się odtworzyć co dokładnie Claude zwrócił. Jedyny trop to pozycja char 1257.

## Analiza przyczyny

### Dlaczego Claude zwrócił zepsuty JSON?

Prompt w `generate_seo_v4()` wymaga od LLM:
1. `article_body` z HTML — **zawiera `<a href="..." target="_blank">`** (instrukcja D10 external links)
2. `external_links` z `anchor_text` i `url`
3. `image_descriptions` z `alt_text`

Claude musi wygenerować JSON string zawierający **HTML z atrybutami w podwójnych cudzysłowach**.
W poprawnym JSONie to wymaga escapowania: `"article_body": "tekst <a href=\"url\" target=\"_blank\">link</a>"`

**Claude czasem zapomina escape'ować cudzysłowy w wartościach JSON.**

Pozycja char 1257 (linia 13, kolumna 330) sugeruje:
- Linia 13 w wygenerowanym JSON to prawdopodobnie `article_body` (długie pole, ~1000-1500 zn)
- Kolumna 330 = w środku treści HTML
- Prawdopodobny wzorzec: `<a href="https://..." target="_blank">` bez escape

### Czy to problem z D10/D11?

**TAK — D10 (external links) zwiększa ryzyko:**
- Przed D10: `article_body` nie zawierał tagów `<a>` — mniejsze ryzyko złamania JSON
- Po D10: prompt wymaga wplecenia `<a href="URL" target="_blank">anchor</a>` w `article_body`
- Podwójne cudzysłowy w atrybutach HTML wewnątrz JSON value string = klasyczny problem LLM

### Czy to powtarzalny problem?

**Prawdopodobnie sporadyczny** — LLM nie zawsze popełnia ten błąd.
Ale D10 zwiększa częstotliwość występowania, ponieważ wymaga więcej zagnieżdżonych cudzysłowów.

## Rekomendacja naprawy

### Priorytet 1: Retry z logowaniem (KRYTYCZNE)

W `core/generator.py`, `generate_seo_v4()`:

```python
# PO json.loads() fail:
try:
    return json.loads(text)
except json.JSONDecodeError as exc:
    # LOGUJ surowy output — kluczowe do debugowania
    logger.error(
        "%s JSON parse failed: %s\nRaw output (first 2000 chars): %s",
        provider, exc, text[:2000],
    )
    # Retry 1 raz
    logger.info("Retrying %s for JSON fix...", provider)
    text2 = _call_llm(prompt, api_key, provider)
    text2 = text2.strip()
    text2 = re.sub(r"^```json\s*", "", text2)
    text2 = re.sub(r"\s*```$", "", text2)
    try:
        return json.loads(text2)
    except json.JSONDecodeError as exc2:
        logger.error(
            "%s retry also failed: %s\nRaw output (first 2000 chars): %s",
            provider, exc2, text2[:2000],
        )
        raise
```

### Priorytet 2: JSON repair attempt

Przed retry, spróbuj naprawić typowe problemy:
```python
import re
# Fix trailing commas before } or ]
def _try_fix_json(raw: str) -> str:
    fixed = re.sub(r',\s*([}\]])', r'\1', raw)
    return fixed
```

### Priorytet 3: Prompt engineering

Dodaj do promptu w `generate_seo_v4()`:
```
KRYTYCZNE: W article_body używaj apostrofów (') zamiast cudzysłowów (") w atrybutach HTML.
Np. <a href='https://...' target='_blank'>link</a>
To zapobiega złamaniu formatowania JSON.
```

---

*vse-analyst-08 | video-seo-engine | 2026-06-21 — raport diagnostyczny JSON error*