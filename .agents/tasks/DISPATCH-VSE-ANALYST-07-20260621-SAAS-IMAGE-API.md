# DISPATCH — A7: Analiza SAAS Image Description API pod D11

**Callsign:** vse-analyst-07  
**Dispatch:** DISPATCH-VSE-ANALYST-07-20260621-SAAS-IMAGE-API  
**Projekt:** video-seo-engine + crimson-void (SAAS)  
**Priorytet:** 🟡 WYSOKI (blokuje finalną architekturę D11)  
**Data:** 2026-06-21  
**Wystawiony przez:** Supervisor 01  

---

## CEL

Zbadaj mechanizm opisu obrazków w SAAS (crimson-void / PressAI) i określ, czy VSE pipeline (D11) powinien użyć SAAS API do generowania opisów screenshotów zamiast ślepego promptowania LLM.

## KONTEKST

D11 (Video Screenshots + ImageObject Schema) wymaga generowania 4 pól opisu dla każdego obrazka:
- **alt text** (alt atrybut, SEO z keyword)
- **title** (tytuł obrazka)
- **caption** (podpis pod obrazkiem)
- **description** (opis w WP Media Library)

Aktualny plan D11: LLM generuje te opisy „ślepo” — nie widzi rzeczywistego thumbnailsa.
SAAS (PressAI) ma wbudowany mechanizm który:
- Rozpoznaje treść obrazka (vision/AI)
- Generuje 4 pola opisu
- Uwzględnia frazy SEO portalu

Jeśli SAAS API to potrafi, to jest LEPSZE rozwiązanie niż ślepe LLM.

## CO ZBADAĆ

### 1. Endpoint SAAS do opisu obrazków

Sprawdź w crimson-void repo:
```
mcp_github_get_file_contents:
  owner: gitomwtyczka
  repo: crimson-void
  branch: main
  path: backend/
```

Szukaj:
- Endpoint który przyjmuje obraz (upload/URL) i zwraca opisy
- Model AI używany do rozpoznawania (Gemini vision? Claude vision? custom?)
- Jakie pola zwraca (alt, title, caption, description?)
- Czy akceptuje kontekst SEO (frazy kluczowe portalu)

### 2. Format request/response

Udokumentuj dokładny format:
- Metoda HTTP (POST)
- Parametry (image file? image URL? keywords?)
- Response schema (jakie pola, max długości, język)

### 3. Dostępność z VSE

- Czy SAAS jest dostępny z VPS (oracle-crimson)? Prawdopodobnie tak — to ta sama maszyna.
- Jaki jest URL? (prawdopodobnie http://172.17.0.1:PORT lub localhost)
- Czy wymaga auth? (JWT? API key?)
- Jak długo trwa przetwarzanie 1 obrazka?

### 4. Rekomendacja architektoniczna

Na podstawie analizy zaproponuj jedno z:

**Opcja A: SAAS-first (preferowana jeśli API istnieje)**
```
YouTube thumbnail → SAAS Image API → alt/title/caption/description z SEO
                                    → upload do WP Media z tymi opisami
```

**Opcja B: LLM-only (fallback jeśli SAAS nie ma tej funkcji)**
```
YouTube thumbnail → LLM prompt (bez widzenia obrazka) → opisy generyczne
                                                     → upload do WP
```

**Opcja C: Hybrid (najlepsza jeśli możliwa)**
```
YouTube thumbnail → SAAS Image API → opisy vision-based
                 → LLM prompt     → kontekst artykułu
                 → merge: SAAS vision + LLM kontekst → finalne opisy
```

## FORMAT RAPORTU

```markdown
# A7: SAAS Image Description API — Analiza

## Endpoint
- URL: ...
- Metoda: ...
- Auth: ...

## Request
- Parametry: ...

## Response
- Pola: ...
- Przykład: ...

## Rekomendacja
- Opcja: A/B/C
- Uzasadnienie: ...
- Zmiany potrzebne w D11: ...
```

## DUAL-WRITE RAPORT

1. Raport do `video-seo-engine/.agents/reports/`
2. Raport do `sonic-void/.agents/reports/inbox/2026-06-21_vse-analyst-07_saas-image-api.md`
3. Heartbeat status: `done`

## UWAGA

> ⚠️ Ten dispatch NIE blokuje D10 (Smart External Links). D10 może jechać równolegle.
> Wynik A7 wpłynie na FINALNĄ implementację D11 — może zmienić Fazę B (kto generuje opisy).

---

*[Supervisor 01 | sonic-void 21.06.2026 00:51] — dispatch A7*