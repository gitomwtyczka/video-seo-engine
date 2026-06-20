# D6b Independent Audit Report — vse-analyst-06

**Dispatch:** DISPATCH-VSE-ANALYST-06-20260620-D6B-AUDIT  
**Auditor:** vse-analyst-06  
**Data audytu:** 2026-06-20 20:23–21:05  
**Worker:** vse-dev-21  
**Scope:** D6b — architektura kanał/witryna/typy publikacji  

---

## 1. Weryfikacja testów workera

Worker raportuje: ✅ KOMPLETNY, 13 commitów, deploy + health OK.

> Worker NIE dostarczył tabeli 30/31 testów — raport zawiera listę commitów. Dispatch mówi o "30/31 ✅" ale worker nie potwierdza tej liczby. Audytor testował niezależnie.

### Testy workera vs audytor

| # | Test | Worker | Audytor | Zgodność |
|---|------|--------|---------|----------|
| T1 | `list_channels()` → `['prawy-tv']` | ✅ | ✅ | ✅ |
| T2 | `load_channel('prawy-tv')` → poprawny dict | ✅ | ✅ | ✅ |
| T3 | `load_profile('prawy')` → portal_id=prawy | ✅ | ✅ | ✅ |
| T4 | `source_channels` w prawy.yaml | ✅ | ✅ | ✅ |
| T5 | `get_channel_for_profile(prawy)` → prawy-tv | ✅ | ✅ | ✅ |
| T6 | `get_default_publication_type(prawy)` → full_analysis | ✅ | ✅ | ✅ |
| T7 | `get_default_publication_type(prawy, 'prawy-tv')` → full_analysis | — | ✅ | ✅ |
| T8 | `load_channel('nonexistent')` → FileNotFoundError | — | ✅ | ✅ |
| T9 | `_validate_channel({}, 'test')` → ValueError | — | ✅ | ✅ |
| T10 | `yt_update_enabled` w prawy-tv.yaml = true | ✅ | ✅ | ✅ |
| T11 | `yt_admin.update_video_title_and_description()` ma `channel` param | — | ✅ (default=None) | ✅ |
| T12 | `_build_key_moments()` istnieje | — | ✅ | ✅ |
| T13 | GenerateRequest ma `publication_type` field | — | ✅ (default='full_analysis') | ✅ |
| T14 | Backward compat: GenerateRequest bez publication_type | — | ✅ | ✅ |
| T15 | GenerateRequest z publication_type='watching_page' | — | ✅ | ✅ |
| T16 | `generate_seo_v4()` ma `publication_type` param | — | ✅ (default='full_analysis') | ✅ |
| T17 | `run_generate()` ma `publication_type` param | — | ✅ | ✅ |
| T18 | `tools/oauth_setup.py` istnieje | ✅ | ✅ | ✅ |
| T19 | channels/ katalog w kontenerze | ✅ | ✅ | ✅ |
| T20 | profile prawy.yaml usunięte inline `yt_oauth` | ✅ | ✅ | ✅ |
| T21 | Deploy VPS — kontenery UP | ✅ | ✅ | ✅ |
| T22 | `/health` → `{"status":"ok","version":"2.0.0"}` | ✅ | ✅ | ✅ |
| T23 | API logs — brak crashy/tracebacków | — | ✅ | ✅ |
| T24 | OpenAPI schema — publication_type optional | — | ✅ | ✅ |
| T25 | Nginx routing: /api/* → 8085 | — | ✅ | ✅ |
| T26 | Nginx routing: /v1/* → 8085 | — | ✅ | ✅ |
| T27 | config_utils.py: resolve_env_vars() | — | ✅ | ✅ |
| T28 | config_utils.py: load_yaml_file() | — | ✅ | ✅ |
| T29 | template.yaml ma source_channels | — | ⚠️ prawy-tv zamiast placeholder | ⚠️ |
| T30 | Invalid publication_type akceptowany | — | ⚠️ Brak walidacji enum | ⚠️ |

**Wynik: 28/30 ✅, 2/30 ⚠️ (niskie ryzyko)**

---

## 2. Wyniki niezależnych testów na VPS

### ✅ Pozytywne

1. **Kontenery stabilne** — vse-api Up 25 min, vse-web Up 2h, brak restartów
2. **Channel loader** — `load_channel('prawy-tv')` zwraca kompletny dict
3. **Profile refaktor** — prawy.yaml nie ma inline yt_oauth, source_channels poprawny
4. **Backward compat API** — GenerateRequest bez publication_type działa (default: full_analysis)
5. **Error handling** — FileNotFoundError i ValueError rzucane poprawnie
6. **yt_admin.py parametryzacja** — channel param ma default=None → stary kod działa
7. **API logs czyste** — brak tracebacków w ostatnich 2h
8. **OpenAPI schema** — publication_type poprawnie zadeklarowane jako optional z defaultem

### ⚠️ Znalezione problemy

| # | Problem | Severity | Opis |
|---|---------|----------|------|
| R1 | publication_type bez walidacji enum | 🟡 NISKI | `GenerateRequest(publication_type='invalid_type')` akceptowany. Brak Literal/Enum. |
| R2 | template.yaml → prawy-tv | 🟡 NISKI | Template powinien mieć placeholder channel, nie real kanał. |
| R3 | Env vars unset outside Docker | 🟢 INFO | Expected behavior. |
| R4 | kurier365 mkdir PermissionError poza dockerem | 🟢 INFO | Pre-existing issue, nie D6b. |

---

## 3. Bug Swagger — Root Cause Analysis

### Symptom
- `https://vse.impresjapr.pl/openapi.json` → **404** (Next.js HTML)
- `https://vse.impresjapr.pl/docs` → **200** ale Next.js HTML (Swagger UI nie ma danych)
- `http://localhost:8085/openapi.json` → **200** ✅ (poprawny JSON wewnętrznie)

### Root Cause

Nginx config VSE server block ma explicit locations dla `/docs`, `/redoc`, `/health` → FastAPI (8085).
Ale **brak** `location /openapi.json` → falls through do catch-all `location /` → **Next.js** (3001) → 404.

Swagger UI na `/docs` ładuje JavaScript który pobiera `/openapi.json`. Przeglądarka → nginx → Next.js → 404 → UI puste.

### Propozycja fixu

```nginx
location = /openapi.json {
    proxy_pass http://172.17.0.1:8085;
    proxy_set_header Host $host;
}
```

Dodać PRZED catch-all `location /`. Exact match (`=`) gwarantuje precyzję.
Po dodaniu: `docker exec crimson-nginx nginx -t && docker exec crimson-nginx nginx -s reload`

---

## 4. Verdict: ✅ D6b PASS

| Kategoria | Wynik |
|-----------|-------|
| Channel loader | ✅ |
| Profile refaktor | ✅ |
| yt_admin.py parametryzacja | ✅ |
| generator.py publication_type | ✅ |
| API backward compat | ✅ |
| Deploy + kontenery | ✅ |
| Swagger bug | 🟡 pre-existing, prosty fix nginx |
| publication_type validation | 🟡 brak enum, niskie ryzyko |

### Rekomendacje

1. **Swagger fix** — dodać location = /openapi.json do nginx (5 min)
2. **Enum validation** — Literal['full_analysis', 'watching_page', 'discover'] na publication_type
3. **Template cleanup** — placeholder channel zamiast prawy-tv w template.yaml

---

*vse-analyst-06 | video-seo-engine | 2026-06-20 20:23–21:05 | raport kompletny*
