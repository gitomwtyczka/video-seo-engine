# DISPATCH — A9: Analiza VTT Cache + Content Deduplication

**Callsign:** vse-analyst-09  
**Dispatch:** DISPATCH-VSE-ANALYST-09-20260621-VTT-CACHE-DEDUP  
**Projekt:** video-seo-engine  
**Priorytet:** 🟡 WYSOKI (architektura przed komercjalizacją)  
**Data:** 2026-06-21  
**Wystawiony przez:** Supervisor 01  

---

## CEL

Zbadaj i zaproponuj architekturę dla dwóch problemów:

### Problem 1: Brak cache VTT

Aktualnie każde generowanie ściąga VTT od nowa (YouTube / Local Runner). Gdy użytkownik chce wygenerować 2-3 artykuły z tego samego wideo (np. analizę + discover + dla innego portalu), VTT jest pobierany za każdym razem.

**Zbadaj:**
- Obecny flow VTT w `core/fetcher.py` i `api/services/pipeline.py`
- Czy jest tabela w DB która mogłaby przechować transkrypt? (sprawdź `transcript_jobs`)
- Rozmiar typowego VTT (KB)
- Propozycja schematu cache: DB vs plik vs S3
- TTL — jak długo trzymać
- Klucz cache: `video_id` + `lang`

### Problem 2: Content deduplication

Gdy ten sam film jest przetwarzany 2x (np. na 2 portale, lub analiza + discover), LLM dostaje identyczny input i może wygenerować bardzo podobny artykuł. To grozi:
- Google Duplicate Content penalty
- Niska wartość SEO drugiego artykułu
- Powtarzanie cytatów, wątków

**Zbadaj:**
- Jak różnicować output LLM dla tego samego wideo:
  - Parametr `angle` / `perspective` w prompcie
  - Przekazanie `previously_used_quotes` do LLM
  - Różne `publication_type` już dają inny format — czy wystarczająco?
  - Temperature / seed variation
- Czy potrzebna tabela `generation_history`: video_id + portal + type + generated_quotes + timestamp
- Jak przekazać kontekst „ten film był już przetworzony” do pipeline

## FORMAT RAPORTU

```markdown
# A9: VTT Cache + Content Dedup — Analiza

## VTT Cache
- Obecny flow: ...
- Propozycja: ...
- Schema DB: ...
- TTL: ...
- Szacowany wpływ na performance: ...

## Content Deduplication  
- Obecny stan: ...
- Propozycje dywersyfikacji: ...
- Schema generation_history: ...
- Rekomendacja: ...

## Estymacja pracochłonności
- VTT cache: X dispatchów, ~Yh
- Content dedup: X dispatchów, ~Yh
```

## ŹRÓDŁA DO ZBADANIA

```
mcp_github_get_file_contents:
  owner: gitomwtyczka
  repo: video-seo-engine
  branch: main
  path: core/fetcher.py

mcp_github_get_file_contents:
  path: api/services/pipeline.py

mcp_github_get_file_contents:
  path: api/models/

mcp_github_get_file_contents:
  path: core/generator.py
```

## DUAL-WRITE

1. `video-seo-engine/.agents/reports/`
2. `sonic-void/.agents/reports/inbox/2026-06-21_vse-analyst-09_vtt-cache-dedup.md`

---

*[Supervisor 01 | sonic-void 21.06.2026 17:22] — dispatch A9*