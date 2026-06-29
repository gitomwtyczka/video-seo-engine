# Raport D15: Bezpieczny Pre-Parse Sanitizer (JSONDecodeError Fix)

**Callsign:** vse-dev-30  
**Data:** 2026-06-29  
**Dispatch:** DISPATCH-VSE-DEV-30-20260629-D15-SANITIZER-FIX  
**Status:** ✅ COMPLETED  

---

## Podsumowanie

Zaimplementowano `_sanitize_llm_json()` w `core/generator.py` — funkcję naprawiającą złamany JSON przed `json.loads()`. Eliminuje błędy 500 spowodowane przez LLM wypluwający surowe HTML z podwójnymi cudzysłowami w atrybutach.

## Podejście techniczne

### Decyzja architektoniczna
Supervisor wskazał `json-repair` jako preferowane podejście. Biblioteka była niedostępna na VPS — zainstalowano `json-repair==0.61.1` przez pip.

### Strategia sanitizera (dwie warstwy)
1. **Fast path:** jeśli `json.loads()` przechodzi — natychmiastowy return bez overhead
2. **PRIMARY:** `json_repair.repair_json()` — rozumie strukturę JSON, zero false positives na multilinii i zagnieżdżonych tagach
3. **FALLBACK (regex):** tylko gdy `ImportError` — konwertuje `attr=\"val\"` → `attr='val'` wyłącznie wewnątrz sekwencji podobnych do atrybutów HTML
4. **Final fallback:** jeśli obie metody zawiodą — zwraca raw text, D12 retry mechanism przejmuje obsługę

### Integracja
- `_sanitize_llm_json()` wywoływana w `generate_seo_v4()` przed `json.loads()` (linia ~470)
- Wywoływana RÓWNIEŻ w D12 retry path — podwójna ochrona

## TDD: Testy napisane PRZED implementacją

Plik: `tests/test_d15_sanitizer.py`  
13 testów podzielonych na klasy:
- `TestPassthrough` — 3 testy: poprawny JSON nie jest korumpowany
- `TestHtmlAttrWithDoubleQuotes` — 3 testy: href, multiple attrs, equation
- `TestOnclickPreservation` — 2 testy: onclick nie jest obcinany
- `TestDispatchSpecTestCase` — 2 testy: dokładnie przypadek z dispatchu
- `TestMultilineBody` — 3 testy: wieloliniowy body, polski tekst, typ zwrotny

## Wyniki testów

```
13/13 test_d15_sanitizer.py PASSED (0.06s)
44/44 pełny suite PASSED (0.18s) — zero regresji
```

## Commity

| SHA | Opis |
|-----|------|
| `31b7cda` | test: D15 _sanitize_llm_json — TDD test suite (przed implementacją) |
| `a8fc7b3` | feat: D15 _sanitize_llm_json() — json-repair PRIMARY + regex FALLBACK |

## Deploy

- VPS: `docker compose -f docker-compose.vse.yml up -d --build vse-api` ✔
- Health check: `{"status":"ok","version":"2.0.0","llm_default":"claude"}` ✔
- json-repair 0.61.1 zainstalowany na VPS ✔

## Co teraz działa

LLM może wypluc:
```json
{"article_body": "To link <a href=\"https://prawy.pl\" target=\"_blank\">tekst</a>"}
```
I zamiast błędu 500 — `_sanitize_llm_json()` to naprawia, `json.loads()` przechodzi, artykuł jest zapisywany.

---

*vse-dev-30 | video-seo-engine | 2026-06-29 18:00+02:00*
