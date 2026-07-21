# Raport: Private Video OAuth Fix

**Agent:** `[vse-dev-01]`  
**Data:** 2026-07-21  
**Temat:** Poprawka pobierania danych prywatnych filmów YouTube przez OAuth

## Status: DONE

### Co zostało zrobione:
1. Przeanalizowano logikę autoryzacji z wykorzystaniem modelu `YouTubeChannel`. Model ten przechowuje jedynie `refresh_token` (nie przechowuje `access_token`).
2. W `api/services/pipeline.py` dodano logikę, która na podstawie `user_id` wyciąga z bazy kanał, weryfikuje dostępność `refresh_token`, a następnie używa go w locie (żądanie POST do `oauth2.googleapis.com/token`) aby uzyskać świeży `access_token`.
3. Przekazano `access_token` z pipeline'u do `core/fetcher.py`.
4. W `core/fetcher.py` zaktualizowano `fetch_metadata_api_v3` aby budował parametry uwzględniając nagłówek `Authorization: Bearer <access_token>`, gdy token jest dostępny, a jako fallback używał publicznego `api_key`.
5. Wdrożono zmiany na środowisko produkcyjne VPS.

### Commity:
- `11d2e54` Fix private video OAuth (fetcher) [vse-dev-01]
- `e924afa` Fix private video OAuth (pipeline) [vse-dev-01]

### Zmiany w plikach:
- `core/fetcher.py` (~L330+): Dodano argument `access_token`, zmieniono sposób budowania URL przy użyciu `urllib.parse.urlencode` z dynamicznymi nagłówkami OAuth.
- `api/services/pipeline.py` (~L400+ i L581+): Dodano logikę generowania tokena dostępowego na podstawie zapisanego `refresh_token` dla podłączonego kanału YouTube. Zmodyfikowano sygnaturę `run_generate` uwzględniając `user_id`.

### Refresh token:
Obecny w modelu (jako `refresh_token_encrypted`, dostępny przez propercję `.refresh_token`). 

### Deploy:
OK (docker compose build + up bez błędów, `vse-api` uruchomiony, logi czyste).