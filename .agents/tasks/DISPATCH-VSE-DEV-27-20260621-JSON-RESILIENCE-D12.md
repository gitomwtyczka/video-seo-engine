# DISPATCH — D12: JSON Resilience Fix (generator.py)

**Callsign:** vse-dev-27  
**Dispatch:** DISPATCH-VSE-DEV-27-20260621-JSON-RESILIENCE-D12  
**Projekt:** video-seo-engine  
**Priorytet:** 🔴 KRYTYCZNY (pipeline pada na produkcji)  
**Data:** 2026-06-21  
**Wystawiony przez:** Supervisor 01  
**Na podstawie:** A8 diagnostyka (analyst-08) — potwierdzona przyczyna: Claude nie escape'uje `"` w HTML atrybutach wewnątrz JSON string  

---

## PRZYCZYNA (zdiagnozowana przez A8)

D10 instruuje LLM wstawić `<a href="URL" target="_blank">` w `article_body`.
Claude generuje HTML z podwójnymi cudzysłowami `"` które łamią JSON string:
```json
{"article_body": "Jak podaje <a href="https://..." target="_blank">Wiki</a>"}
```
Parser pada: `Expecting ',' delimiter: line 13 column 330 (char 1257)`

## TRZY ZMIANY (wszystkie w `core/generator.py`)

### 1. MUST — Logowanie surowego LLM output przy `json.loads()` fail

W `generate_seo_v4()`, w bloku `try/except` przy `json.loads(text)`:

```python
try:
    return json.loads(text)
except json.JSONDecodeError as e:
    # NOWE: loguj surowy output do debugowania
    logger.error(
        "JSON parse failed at char %d: %s\nRaw LLM output (first 2000 chars):\n%s",
        e.pos, e.msg, text[:2000]
    )
    raise
```

Bez tego jesteśmy ślepi — nie wiemy co LLM zwrócił.

### 2. MUST — 1 retry przy JSONDecodeError

Po złapanym błędzie, wysłij do LLM krótki retry prompt:

```python
except json.JSONDecodeError as e:
    logger.error("JSON parse failed at char %d: %s\nRaw output: %s", e.pos, e.msg, text[:2000])
    
    # RETRY: poproś LLM o naprawę
    retry_prompt = (
        "Twoja poprzednia odpowiedź zawierała błąd składni JSON "
        f"(pozycja {e.pos}: {e.msg}).\n"
        "Napraw i zwróć TYLKO poprawny JSON. "
        "UWAGA: W polach HTML (article_body) używaj apostrofów (') "
        "zamiast cudzysłowów (\") w atrybutach HTML, np: "
        "<a href='https://...' target='_blank'>\n\n"
        f"Oryginalna odpowiedź do naprawy:\n{text}"
    )
    logger.info("Retrying LLM with fix prompt...")
    text2 = _call_llm(retry_prompt, api_key, provider)
    text2 = text2.strip()
    text2 = re.sub(r"^```json\\s*", "", text2)
    text2 = re.sub(r"\\s*```$", "", text2)
    try:
        return json.loads(text2)
    except json.JSONDecodeError as e2:
        logger.error("RETRY also failed at char %d: %s\nRetry output: %s", e2.pos, e2.msg, text2[:2000])
        raise
```

Max 1 retry — nie więcej (koszt API).

### 3. SHOULD — Prompt engineering: apostrofy zamiast cudzysłowów w HTML

W głównym prompcie `generate_seo_v4()`, w instrukcji do `article_body` (punkt 8) DODAJ:

```
   KRYTYCZNE DLA JSON: W tagach HTML używaj APOSTROFÓW (') zamiast cudzysłowów (") w atrybutach.
   Przykład poprawny: <a href='https://example.com' target='_blank'>tekst</a>
   Przykład BŁĘDNY: <a href="https://example.com" target="_blank">tekst</a>
   Podwójne cudzysłowy w atrybutach HTML ŁAMIĄ format JSON.
```

Dodaj tę samą instrukcję w punkcie 15 (external_links).

## WERYFIKACJA

1. Deploy na VPS
2. Wygeneru artykuł z tego samego URL co błąd: `https://www.youtube.com/watch?v=vWaaDIXMb1M`
   - Portal: Kurier365.pl
   - Typ: watching_page
3. Powinno działać bez błędu
4. Sprawdź w logach czy linki w article_body używają apostrofów

## DEPLOY

```powershell
ssh -i ~/.ssh/oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 \
  'cd /home/ubuntu/video-seo-engine && git pull origin main && docker compose -f docker-compose.vse.yml build vse-api && docker compose -f docker-compose.vse.yml up -d vse-api && sleep 3 && curl -s http://localhost:8085/health'
```

## DUAL-WRITE RAPORT

1. `video-seo-engine/.agents/reports/`
2. `sonic-void/.agents/reports/inbox/2026-06-21_vse-dev-27_D12-json-resilience.md`
3. Heartbeat: `done`

---

*[Supervisor 01 | sonic-void 21.06.2026 16:33] — dispatch D12*