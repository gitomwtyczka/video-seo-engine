# D9 Dashboard Portal Selector — Raport implementacji

**Callsign:** vse-dev-23  
**Data:** 2026-06-20  
**Status:** ✅ DONE  

---

## CO zrobiono

Dodano dropdown wyboru portalu (profilu) i typu publikacji do dashboardu VSE,
umożliwiając testowanie D6b (multi-site) i D7 (SEO scoring).

## Zmiany

### Backend (4 commity)

| Plik | Zmiana | Commit |
|------|--------|--------|
| `api/routers/profiles.py` | **[NEW]** GET /v1/profiles — listuje aktywne profile YAML | f5a1c1d |
| `api/main.py` | Rejestracja profiles router | 456ccbd |
| `api/models/request.py` | `profile_id: Optional[str]` w GenerateRequest | 31f0e21 |
| `api/routers/generate.py` | Przekazanie profile_id do pipeline | b721815 |
| `api/services/pipeline.py` | Ładowanie profilu YAML, użycie site_brand + site_url z profilu | 14737cf |

### Frontend (2 commity)

| Plik | Zmiana | Commit |
|------|--------|--------|
| `web/src/app/dashboard/use-profiles.ts` | **[NEW]** Hook `useProfiles()` | ad96b67 |
| `web/src/app/dashboard/dashboard-inner.tsx` | Dropdown "Portal docelowy" + "Typ publikacji" przed formularzem URL | a328827 |

### Pipeline flow

```
Dashboard:
  1. useProfiles() → GET /v1/profiles → [{id: "prawy", display_name: "Prawy.pl", ...}]
  2. User wybiera profil + typ publikacji
  3. handleGenerate() → POST /v1/generate {profile_id, publication_type}
  4. Pipeline: _load_profile_config("prawy") → profiles/prawy.yaml
     → site_brand = "Prawy TV"
     → site_url = prawy.pl (dla SAAS enrichment)
     → publication_type = "full_analysis" (lub wybrany przez usera)
```

## Weryfikacja

- ✅ `GET /v1/profiles` → 2 profile (Prawy.pl + Kurier365.pl)
- ✅ `GET /health` → ok, v2.0.0
- ✅ Dashboard buduje się bez błędów JS (Next.js build clean)
- ✅ Deploy na VPS — oba kontenery (vse-api, vse-web) restartowane

## Backward Compatibility

- `profile_id` jest Optional — brak profilu = fallback na .env
- `publication_type` ma default "full_analysis" — istniejące wywołania działają
- Endpoint /v1/profiles jest publiczny (lista profili nie zawiera credentials)
