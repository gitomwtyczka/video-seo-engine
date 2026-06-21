# D12: JSON Resilience Fix — Raport

**Callsign:** vse-dev-27  
**Dispatch:** DISPATCH-VSE-DEV-27-20260621-JSON-RESILIENCE-D12  
**Data:** 2026-06-21  
**Commit:** `036f79c9` (core/generator.py)  
**Status:** ✅ COMPLETE — zweryfikowane na produkcji

---

## Co zrobiono

3 zmiany w `core/generator.py` per diagnoza A8 (Claude nie escape'uje `"` w HTML atrybutach wewnątrz JSON string):

### 1. MUST — Logowanie surowego LLM output przy json.loads() fail
- W `generate_seo_v4()`, blok `except json.JSONDecodeError`
- `logger.error()` z pierwszymi 2000 znakami raw LLM output
- Bez tego byliśmy ślepi — nie wiedzieliśmy co LLM zwrócił

### 2. MUST — 1 retry przy JSONDecodeError
- Po złapanym błędzie, wysyłamy retry prompt do LLM
- Retry instruuje: "napraw JSON, użyj apostrofów zamiast cudzysłowów w HTML"
- Max 1 retry (koszt API), jeśli retry też fail → raise

### 3. SHOULD — Prompt engineering: apostrofy zamiast cudzysłowów
- Punkt 8 (article_body): zmieniono format linków na `<a href='URL' target='_blank'>`
- Dodano sekcję "KRYTYCZNE ZASADY FORMATU JSON" z jasnymi instrukcjami
- Punkt 15 (external_links): dodano ostrzeżenie o nie-używaniu podwójnych cudzysłowów
- Dodano docstring D12 w module header

## Weryfikacja

- **Deploy:** VPS build + restart kontener → health check OK
- **Test:** `POST /v1/generate` z `video_url=vWaaDIXMb1M`, `wp_url=kurier365.pl`, `publication_type=watching_page`
- **Wynik:** `status: ok`, `processing_time: 84.1s`
- **article_body:** HTML linki używają apostrofów: `<a href='https://www.prezydent.pl' target='_blank'>`
- **Retry:** NIE był potrzebny — prompt fix zadziałał prewencyjnie od pierwszego call
- **JSON:** sparsowany poprawnie za pierwszym razem

## Root cause (z A8)

D10 (Smart External Links) dodał instrukcję wplecenia `<a href="URL" target="_blank">` w article_body.
Claude wstawił HTML z podwójnymi cudzysłowami `"` bez escape'owania → `json.loads()` crash.

**Fix:** prompt mówi LLM żeby użył `'` (apostrofów) w HTML attrs + retry layer jako safety net.

---

*[vse-dev-27 | video-seo-engine 2026-06-21 17:12]*