# DISPATCH — A8: Diagnostyka błędu JSON parsing w pipeline

**Callsign:** vse-analyst-08  
**Dispatch:** DISPATCH-VSE-ANALYST-08-20260621-JSON-ERROR-DIAG  
**Projekt:** video-seo-engine  
**Priorytet:** 🔴 KRYTYCZNY (pipeline nie działa)  
**Data:** 2026-06-21  
**Wystawiony przez:** Supervisor 01  

---

## CEL

Zdiagnozuj przyczynę błędu który pojawił się na dashboardzie VSE:

```
Wystąpił błąd
Expecting ',' delimiter: line 13 column 330 (char 1257)
```

Kontekst ze screena:
- Portal: Kurier365.pl
- Typ publikacji: Strona z filmem (watching_page)
- URL: https://www.youtube.com/watch?v=vWaaDIXMb1M
- Wersja API: 2.0.0

## CO ZROBIĆ

### 1. Sprawdź logi VPS

```bash
ssh -i ~/.ssh/oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 \
  'docker logs vse-api --tail 200 2>&1 | grep -A 20 "ERROR\|Traceback\|JSONDecodeError\|Expecting"'
```

Szukaj:
- Pełnego traceback’a — która funkcja, który plik, która linia
- Surowego LLM output (jeśli logowany) — co dokładnie LLM zwrócił
- Czy błąd jest w generator.py (LLM output parsing) czy gdzie indziej

### 2. Sprawdź pełny traceback

```bash
ssh -i ~/.ssh/oracle-crimson.key -o StrictHostKeyChecking=no ubuntu@147.224.162.100 \
  'docker logs vse-api --tail 500 2>&1'
```

### 3. Sprawdź czy to nowy błąd (D10/D11) czy stary

Porównaj:
- Czy błąd występuje TYLKO z profilem Kurier365.pl?
- Czy występuje z profilem Prawy.pl też?
- Czy występuje z różnymi typami publikacji?
- Czy występował PRZED commitami D10/D11?

### 4. Jeśli to LLM output — pokaż surowy output

Jeśli błąd jest w `json.loads()` w generator.py, znajdź i pokaż:
- Dokładny tekst który LLM zwrócił (lub fragment wokół char 1257)
- Który provider (Gemini/Claude)
- Czy prompt był poprawnie złożony (bez uciecia, bez duplikatów)

### 5. Jeśli to NIE LLM output — zidentyfikuj źródło

Możliwe inne przyczyny:
- Błąd w nowym kodzie D11 (pipeline.py: `_describe_image_via_saas()` response parsing)
- Błąd w profilu Kurier365.pl (YAML loading)
- Błąd w SAAS enrichment response
- Błąd w endpoint API (request body parsing)

## FORMAT RAPORTU

```markdown
# A8: Diagnostyka JSON Error

## Traceback
[pełny traceback z logów]

## Przyczyna
[dokładna przyczyna z dowodem]

## Dowody
- [logi, fragmenty kodu, surowy output]

## Rekomendacja naprawy
- [konkretna zmiana w konkretnym pliku]
```

## DUAL-WRITE RAPORT

1. `video-seo-engine/.agents/reports/`
2. `sonic-void/.agents/reports/inbox/2026-06-21_vse-analyst-08_json-error-diag.md`

---

*[Supervisor 01 | sonic-void 21.06.2026 16:16] — dispatch A8 diagnostyka*