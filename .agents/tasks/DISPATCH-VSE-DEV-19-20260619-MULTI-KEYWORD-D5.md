# DISPATCH-VSE-DEV-19-20260619-MULTI-KEYWORD-D5

**Data:** 2026-06-19  
**Supervisor:** Supervisor 01  
**Agent:** `vse-dev-19`  
**Projekt:** video-seo-engine | branch: main  
**Priorytet:** HIGH  
**Podstawa:** Raport `vse-analyst-03` — A2: RankMath API Focus Keywords

---

## Cel

Aktualnie VSE wysyła do RankMath tylko jeden focus keyword. Analiza (vse-analyst-03) wykazała:
1. RankMath akceptuje comma-separated string: `"fraza1,fraza2,fraza3"` — pierwsza = Primary
2. Generator produkuje tylko `focus_keyphrase` (singular) — brak multi-keyword
3. SAAS `priority_keywords` trafiają do promptu LLM ale NIE do `rank_math_focus_keyword`

---

## Zadanie D5 — Multiple Focus Keywords

### D5.1 — Generator: rozszerz output

**Plik:** `core/generator.py` → `generate_seo_v4()`

Zmień odpowiedź JSON z:
```json
{ "focus_keyphrase": "fraza główna" }
```
Na:
```json
{ 
  "focus_keyphrase": "fraza główna",
  "focus_keyphrases": ["fraza główna", "fraza2", "fraza3"]
}
```

W prompcie LLM: poproś o 2-4 dodatkowe frazy kluczowe powiązane tematycznie. Max 5 łącznie.
Backward compat: `focus_keyphrase` (singular) musi pozostać jako primary.

### D5.2 — Injector: multi-keyword do RankMath

**Plik:** `core/injector.py` → funkcja wysyłająca `rank_math_focus_keyword`

Logika:
```python
keyphrases = seo.get('focus_keyphrases', [seo.get('focus_keyphrase', '')])
# Doklejamy priority_keywords z SAAS jeśli są dostępne
if priority_keywords:  # lista ze SEO Package / pipeline.py
    keyphrases = priority_keywords[:2] + keyphrases  # SAAS keywords na czoło
rankmath_kw = ','.join(keyphrases[:5])  # max 5, comma-separated
```

Następnie `rankmath_kw` trafia do `rank_math_focus_keyword` w payloadzie `updateMeta`.

### D5.3 — Pipeline: przekazanie priority_keywords

**Plik:** `core/pipeline.py` (lub odpowiednik wywołujący inject_video)

Sprawdź czy `priority_keywords` (z SAAS enrichment) jest dostępne w tym momencie pipeline'u. Jeśli tak — przekaż do `inject_video()`. Jeśli nie — dokumentuj jako NEXTSTEP.

### D5.4 — Fix: Quotation schema (bonus, niski koszt)

Według raportu vse-analyst-03 (R3): Quotation schema jest zbędna — Google NIE renderuje jej w rich results. Usuń ~10 linii z `build_schema_jsonld()` w `core/injector.py`.

**Warunek:** Wykonaj D5.4 TYLKO jeśli nie ryzykuje to regresji w innych testach. Jeśli ryzykuje — pomiń i zanotuj.

---

## Uwagi dotyczące duplikatu VideoObject (R1 z raportu)

> **Nie implementuj tego w kodzie.** To jest kwestia konfiguracji WordPress.

Zapisz notatkę w raporcie: "RankMath Auto-detect video wymaga wyłączenia w panelu WP → RankMath → Schema → Video → Auto-detect". Administrator WP wykonuje ręcznie.

---

## Weryfikacja

- `generate_seo_v4()` zwraca `focus_keyphrases: []` (lista)
- `rank_math_focus_keyword` w payloadzie to comma-separated string z ≥2 frazami
- Backward compat: `focus_keyphrase` (singular) nadal istnieje w output
- Graceful degradation: jeśli `focus_keyphrases` absent — fallback do singular
- (opcjonalnie) Quotation schema usunięta bez błędów

---

## Raportowanie

Po zakończeniu:
1. Raport do `video-seo-engine/.agents/reports/2026-06-19_vse-dev-19_multi-keyword-d5.md`
2. Kopia do `sonic-void/.agents/reports/inbox/2026-06-19_vse-dev-19_multi-keyword-d5.md`
3. Heartbeat `status: done`

---

*Supervisor 01 | video-seo-engine | 2026-06-19*
