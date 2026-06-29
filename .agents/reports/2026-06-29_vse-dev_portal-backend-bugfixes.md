# Raport: Portal Backend + Bugfixes

**CO:**
Zakończono implementację backendu dla zarządzania portalami (DISPATCH-VSE-DEV-20260629-03A-PORTAL-BACKEND).
Dodatkowo rozwiązano dwa błędy (BUG #1, BUG #2) w `core/injector.py`.

**PO CO:**
- Nowe kolumny oraz endpointy dla portali (Profile ID) pozwalają na wielodostępne działanie generatora.
- Pipeline został zmodyfikowany (`generate.py`, `pipeline.py`), aby wykorzystywać `portal_id` z zapytania zamiast `profile_id`.
- Poprawki dla RankMath zabezpieczają pustą odpowiedź (BUG #1), co powodowało błędy JSON decode.
- Użycie odpowiedniego `site_brand` naprawia problem hardcoded "Prawy TV" w alt tekstach (BUG #2).
- Dodano `json-repair` do dependencies w celu zwiększenia stabilności.

**JAK:**
1. Zaktualizowano `api/models/job.py`, dodając kolumnę `portal_id` dla przekazywania ID portalu z fazy generate do inject.
2. Zaktualizowano `api/routers/generate.py`, aby zapisywał `portal_id` w `TranscriptJob`.
3. Zaktualizowano `api/services/pipeline.py` (funkcja `run_inject`), by na podstawie `video_url` pobierał `portal_id` z job'a, a z bazy portalowych settings doczytywał `profile_config`.
4. Poprawiono błędy w `core/injector.py`:
   - W `update_rankmath_meta()` zaimplementowano blok try/except + obsługę pustego body.
   - W `inject_video()` wprowadzono użycie wartości `site_brand` z `profile` lub `saas_data` zamiast sztywnej wartości "Prawy TV".
5. Dodano `json-repair` do `requirements.txt`.
6. Kod na zdalnym repozytorium GitHub został zaktualizowany bezpośrednio używając narzędzi MCP.

**BLOKERY / DEPLOY:**
Instrukcja z dispatcha nakazywała deploy na VPS za pomocą `ssh`. Zgodnie z regułami `AGENTS.md` (ZAKAZ W SESJACH PROJEKTOWYCH) polecenie to zostało wstrzymane. Deploy musi zostać wykonany przez dedykowaną sesję.
