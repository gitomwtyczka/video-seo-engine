---
dispatch_id: "VSE-DEV-19-D5-MULTI-KEYWORD"
created: "2026-06-19"
updated: "2026-06-20 — rev.2 po analizie kodu i decyzjach usera"
supervisor: "Supervisor 01"
assigned_to: "[vse-dev-19]"
repo: "video-seo-engine + crimson-void (cross-repo)"
branch: "main"
priority: "HIGH"
status: "dispatched"
---

# DISPATCH D5 — Multi-keyword RankMath + Trends (cross-repo)

## Kontekst

### Problem
- Generator LLM produkuje **jeden** `focus_keyphrase` (singular)
- RankMath akceptuje **do 5 fraz** oddzielonych przecinkami
- SAAS (PressAI) posiada `priority_keywords` z GSC — trafiają do promptu LLM, ale **NIE** do `rank_math_focus_keyword`
- Google Trends jest zaimplementowany w SAAS (`backend/context_intelligence.py` — klasa `ContextIntelligenceLayer`, metoda `_fetch_trends_context`) ale NIE jest eksponowany przez endpoint `/api/external/seo-data`

### Cel
RankMath widzi 3-5 fraz z trzech źródeł: GSC → Trends → LLM.

---

## Zadanie — 4 kroki

### Krok 1: SAAS (crimson-void) — rozszerz endpoint o Trends

**Repo:** `crimson-void` | branch: `main`

Endpoint `/api/external/seo-data` aktualnie zwraca:
```json
{"keywords": [...], "top_pages": [...], "gsc_status": "ok"}
```

Dodaj pole `trends_keywords`:
```json
{"keywords": [...], "top_pages": [...], "gsc_status": "ok", "trends_keywords": ["fraza1", "fraza2"]}
```

**Jak:**
- Znajdź router/endpoint dla `/api/external/seo-data` w `backend/`
- Wywołaj `ContextIntelligenceLayer._fetch_trends_context(topic)` (już istnieje)
- Parsuj wynik (format: `"- fraza1\n- fraza2"`) na listę stringów
- Dorzuć jako `trends_keywords: []` do response
- Graceful: jeśli Trends nie zwróci danych → `trends_keywords: []`
- **~15 linii kodu**

---

### Krok 2: VSE — saas_enricher odczytuje Trends

**Repo:** `video-seo-engine` | branch: `main`  
**Plik:** `api/services/saas_enricher.py`

W `get_saas_seo_data()` — dodaj odczyt nowego pola:
```python
result = {
    "keywords": data.get("keywords", []),
    "top_pages": data.get("top_pages", []),
    "trends_keywords": data.get("trends_keywords", []),  # NOWE
    "gsc_status": data.get("gsc_status", "ok"),
    ...
}
```

Dodaj helper:
```python
def extract_trends_keywords(saas_data: dict) -> list[str]:
    return saas_data.get("trends_keywords", [])
```

**~10 linii.**

---

### Krok 3: VSE — Generator zwraca listę keyphrases

**Plik:** `core/generator.py`

Aktualnie LLM prompt żąda:
```
"focus_keyphrase": "jedna fraza"
```

Zmień na:
```
"focus_keyphrases": ["fraza główna", "fraza 2", "fraza 3"]
```

- Backward compat: jeśli LLM zwróci stary format `focus_keyphrase` (string) — wrap w listę
- Max 3 frazy od LLM (GSC i Trends dorzucają resztę)

---

### Krok 4: VSE — Injector merge → RankMath

**Plik:** `core/injector.py`

Aktualna logika:
```python
rank_math_focus_keyword = seo_data.get("focus_keyphrase", "")
```

Nowa logika:
```python
def build_focus_keywords(seo_data: dict, saas_data: dict) -> str:
    """Merge keywords: GSC top2 + Trends + LLM → comma-separated for RankMath."""
    keywords = []
    
    # 1. GSC priority (top 2)
    gsc_kw = extract_priority_keywords(saas_data, max_keywords=2)
    keywords.extend(gsc_kw)
    
    # 2. Trends (top 2)
    trends_kw = extract_trends_keywords(saas_data)
    keywords.extend(trends_kw[:2])
    
    # 3. LLM-generated
    llm_kw = seo_data.get("focus_keyphrases", [])
    if isinstance(llm_kw, str):  # backward compat
        llm_kw = [llm_kw]
    keywords.extend(llm_kw)
    
    # Dedupe, max 5
    seen = set()
    unique = []
    for kw in keywords:
        kw_lower = kw.strip().lower()
        if kw_lower and kw_lower not in seen:
            seen.add(kw_lower)
            unique.append(kw.strip())
    
    return ",".join(unique[:5])
```

**~25 linii.**

---

## ⚠️ Quotation schema

**NIE usuwaj Quotation schema.** Zostaje — będzie używana w D6b do budowania opisu YT z cytatami i timestampami.

---

## Weryfikacja

- [ ] SAAS endpoint zwraca `trends_keywords` (lub puste `[]`)
- [ ] VSE `saas_enricher.py` czyta `trends_keywords`
- [ ] Generator produkuje `focus_keyphrases: []` (lista)
- [ ] Backward compat: stary `focus_keyphrase` (string) nadal działa
- [ ] Injector merguje GSC + Trends + LLM → max 5 fraz
- [ ] `rank_math_focus_keyword` zawiera comma-separated frazy
- [ ] Serwis działa po deploy (user weryfikuje)

---

## Raportowanie

1. `video-seo-engine/.agents/reports/2026-06-20_vse-dev-19_multi-keyword-d5.md`
2. `sonic-void/.agents/reports/inbox/2026-06-20_vse-dev-19_multi-keyword-d5.md`

---

*Supervisor 01 | video-seo-engine | 2026-06-20 rev.2*
